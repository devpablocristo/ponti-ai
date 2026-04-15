"""Un turno de chat asistente Ponti: orquestación LLM + tools + persistencia."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Literal

from runtime import (
    OUTPUT_KIND_CHAT_REPLY,
    ROUTING_SOURCE_ORCHESTRATOR,
    ROUTING_SOURCE_READ_FALLBACK,
    ROUTING_SOURCE_UI_HINT,
)
from runtime.api.events import to_sse_event
from runtime.chat.blocks import build_text_block
from runtime.domain.models import LLMProvider, Message
from runtime.logging import get_logger
from runtime.orchestrator import OrchestratorLimits, orchestrate
from runtime.text import estimate_tokens

from src.agents.catalog import (
    CAMPAIGNS_AGENT_NAME,
    DASHBOARD_AGENT_NAME,
    INSIGHT_CHAT_AGENT_NAME,
    LABORS_AGENT_NAME,
    LOTS_AGENT_NAME,
    PRODUCT_AGENT_NAME,
    REPORTS_AGENT_NAME,
    STOCK_AGENT_NAME,
    SUPPLIES_AGENT_NAME,
    normalize_routed_agent,
    normalize_routing_source,
)
from src.config import Settings
from src.core.dossier import (
    build_project_operating_context_for_prompt,
    capture_turn_memory,
    sync_chat_handoff,
    sync_dashboard_snapshot,
    sync_insights_snapshot,
    sync_project_from_backend,
)
from src.core.system_prompt import base_system_prompt, route_system_addon
from src.db.repository import AIRepository
from src.runtime_contracts import ROUTING_SOURCE_INSIGHT_CHAT_AGENT
from src.agents.audit import record_agent_event
from src.agents.insight_chat_service import (
    compact_insight_evidence_for_prompt,
    extract_insight_evidence,
)
from src.tools.ponti_backend import PontiBackendClient
from src.tools.registry import build_ponti_tool_declarations, build_ponti_tool_handlers

logger = get_logger(__name__)

_EXECUTIVE_CUES: tuple[str, ...] = (
    "cómo viene", "como viene", "mirada de dueño", "mirada de dueno",
    "resumen ejecutivo", "salud del proyecto", "estado del proyecto",
    "qué harías", "que harias", "qué conviene", "que conviene",
    "prioridades", "riesgos", "acciones concretas",
    "plan de acción", "plan de accion", "desvío", "desvio", "resultado operativo",
)

_FOLLOW_UP_CUES: tuple[str, ...] = (
    "explicame", "explícame", "por qué", "por que",
    "y entonces", "qué hago", "que hago",
    "seguí", "segui", "desarrollá", "desarrolla",
    "profundizá", "profundiza", "detallá", "detalla",
)


def _looks_executive_request(message: str) -> bool:
    return any(cue in message for cue in _EXECUTIVE_CUES)


def _looks_like_contextual_follow_up(message: str) -> bool:
    return any(cue in message for cue in _FOLLOW_UP_CUES)


def _looks_like_insight_chat_request(message: str, chat_context: dict[str, Any] | None) -> bool:
    if isinstance(chat_context, dict):
        if any(str(chat_context.get(key) or "").strip() for key in ("notification_id", "insight_id")):
            return True
        if str(chat_context.get("source_kind") or chat_context.get("kind") or "").strip().lower() in {"insight", "approval", "insight_digest"}:
            return True
    return any(token in message for token in ("explicame este insight", "explicá este insight", "explain this insight"))


def _normalize_explicit_route_hint(route_hint: str | None) -> str | None:
    if route_hint is None:
        return None
    normalized = normalize_routed_agent(route_hint)
    if normalized == PRODUCT_AGENT_NAME:
        return None
    return normalized


def _infer_read_route(message: str) -> str | None:
    if _looks_executive_request(message) or any(k in message for k in ("insight", "resumen", "panorama", "alerta", "métrica", "metrica", "dashboard")):
        return DASHBOARD_AGENT_NAME
    if any(k in message for k in ("labor", "laboreo", "jornal", "contratista")):
        return LABORS_AGENT_NAME
    if any(k in message for k in ("insumo", "insumos", "abastecimiento")):
        return SUPPLIES_AGENT_NAME
    if "campaña" in message or "campana" in message:
        return CAMPAIGNS_AGENT_NAME
    if "lote" in message:
        return LOTS_AGENT_NAME
    if any(k in message for k in ("stock", "existencia", "inventario")):
        return STOCK_AGENT_NAME
    if any(k in message for k in ("informe", "reporte", "export")):
        return REPORTS_AGENT_NAME
    return None


def _carry_forward_route(message: str, dossier: dict[str, Any] | None) -> str | None:
    if not isinstance(dossier, dict):
        return None
    workspace = dossier.get("workspace", {})
    if not isinstance(workspace, dict):
        return None
    last_route = normalize_routed_agent(str(workspace.get("last_route_hint") or ""))
    if last_route == PRODUCT_AGENT_NAME:
        return None
    if last_route == INSIGHT_CHAT_AGENT_NAME:
        ic_context = dossier.get("insight_chat_context", {})
        if isinstance(ic_context, dict) and any(str(ic_context.get(key) or "").strip() for key in ("notification_id", "insight_id")):
            if _looks_like_contextual_follow_up(message):
                return INSIGHT_CHAT_AGENT_NAME
        return None
    if _looks_like_contextual_follow_up(message):
        return last_route
    return None


def _resolve_route(route_hint: str | None, message: str, *, chat_context: dict[str, Any] | None = None, dossier: dict[str, Any] | None = None) -> tuple[str, str]:
    ml = message.lower()
    explicit = _normalize_explicit_route_hint(route_hint)
    if explicit is not None:
        if _looks_executive_request(ml) and explicit in {PRODUCT_AGENT_NAME, SUPPLIES_AGENT_NAME, LABORS_AGENT_NAME, CAMPAIGNS_AGENT_NAME, LOTS_AGENT_NAME, STOCK_AGENT_NAME}:
            return DASHBOARD_AGENT_NAME, ROUTING_SOURCE_ORCHESTRATOR
        if explicit == INSIGHT_CHAT_AGENT_NAME and _looks_like_insight_chat_request(ml, chat_context):
            return INSIGHT_CHAT_AGENT_NAME, ROUTING_SOURCE_INSIGHT_CHAT_AGENT
        return explicit, ROUTING_SOURCE_UI_HINT

    carried = _carry_forward_route(ml, dossier)
    if carried is not None:
        if carried == INSIGHT_CHAT_AGENT_NAME:
            return carried, ROUTING_SOURCE_INSIGHT_CHAT_AGENT
        return carried, ROUTING_SOURCE_UI_HINT

    if _looks_like_insight_chat_request(ml, chat_context):
        return INSIGHT_CHAT_AGENT_NAME, ROUTING_SOURCE_INSIGHT_CHAT_AGENT

    read_route = _infer_read_route(ml)
    if read_route is not None:
        return read_route, ROUTING_SOURCE_READ_FALLBACK

    return PRODUCT_AGENT_NAME, ROUTING_SOURCE_ORCHESTRATOR


def _history_to_messages(history: list[dict[str, Any]], limit: int = 24) -> list[Message]:
    result: list[Message] = []
    for item in history[-limit:]:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", ""))
        if role not in {"user", "assistant", "tool"}:
            continue
        if role == "tool":
            tcid = str(item.get("tool_call_id") or item.get("name") or "tool")
            result.append(Message(role="tool", content=content, tool_call_id=tcid))
        else:
            result.append(Message(role=role, content=content))
    return result


def _resolve_language(preferred: str | None, accept_language: str | None) -> Literal["es", "en"]:
    p = (preferred or "").strip().lower()
    if p.startswith("en"):
        return "en"
    if p.startswith("es"):
        return "es"
    if accept_language and re.search(r"\ben\b", accept_language.lower()):
        return "en"
    return "es"


def _orchestrator_limits(settings: Settings) -> OrchestratorLimits:
    tool_to = max(5.0, float(settings.ponti_backend_timeout_ms) / 1000.0)
    total_to = max(45.0, min(300.0, float(settings.llm_timeout_ms) / 1000.0 * 25))
    return OrchestratorLimits(
        max_tool_calls=int(settings.chat_max_tool_calls),
        tool_timeout_seconds=tool_to,
        total_timeout_seconds=total_to,
    )


def _should_refresh(last_value: str | None, ttl_seconds: int) -> bool:
    if not last_value:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last_value).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(UTC) - last_dt).total_seconds() >= ttl_seconds


def _compact(value: Any) -> str:
    return str(value or "").strip()


async def _refresh_project_dossier(
    *,
    dossier: dict[str, Any],
    project_id: str,
    user_id: str,
    routed: str,
    user_message: str,
    settings: Settings,
    backend: PontiBackendClient,
    get_summary,
) -> dict[str, Any]:
    project = dossier.setdefault("project", {})
    if backend.is_configured() and _should_refresh(
        _compact(project.get("last_backend_refresh_at")),
        int(settings.chat_project_context_ttl_seconds),
    ):
        project_payload = await backend.get_json(f"/api/v1/projects/{project_id}", user_id=user_id, params=None)
        if project_payload.get("ok"):
            sync_project_from_backend(dossier, project_payload)

    insights_snapshot = dossier.setdefault("insights_snapshot", {})
    if _should_refresh(
        _compact(insights_snapshot.get("last_refreshed_at")),
        int(settings.chat_project_context_ttl_seconds),
    ):
        def _run_summary() -> dict[str, Any]:
            summary = get_summary.handle(project_id)
            return {
                "new_count_total": summary.new_count_total,
                "new_count_high_severity": summary.new_count_high_severity,
                "top_titles": [item.title for item in summary.top_insights[:5]],
            }
        summary_payload = await asyncio.to_thread(_run_summary)
        sync_insights_snapshot(
            dossier,
            new_count_total=int(summary_payload["new_count_total"]),
            new_count_high_severity=int(summary_payload["new_count_high_severity"]),
            top_titles=list(summary_payload["top_titles"]),
        )

    if backend.is_configured() and (
        routed in {"dashboard", "reports", "stock", "lots", "insight_chat"} or _looks_executive_request(user_message.lower())
    ) and _should_refresh(
        _compact(project.get("last_dashboard_refresh_at")),
        int(settings.chat_dashboard_context_ttl_seconds),
    ):
        dashboard_payload = await backend.get_json(
            "/api/v1/dashboard",
            user_id=user_id,
            params={"project_id": int(str(project_id).strip())},
        )
        if dashboard_payload.get("ok"):
            sync_dashboard_snapshot(dossier, dashboard_payload)
    return dossier


_MENU_CUES = ("menú", "menu", "opciones", "categorías", "categorias", "ayuda")
_AMBIGUOUS_CUES = ("cuánto hay", "cuanto hay", "dame el resumen", "resumen", "qué onda", "que onda")

_DOMAIN_CATEGORIES: list[dict[str, str]] = [
    {"label": "Tablero / Insights", "route_hint": DASHBOARD_AGENT_NAME},
    {"label": "Labores", "route_hint": LABORS_AGENT_NAME},
    {"label": "Insumos", "route_hint": SUPPLIES_AGENT_NAME},
    {"label": "Lotes", "route_hint": LOTS_AGENT_NAME},
    {"label": "Stock", "route_hint": STOCK_AGENT_NAME},
    {"label": "Campañas", "route_hint": CAMPAIGNS_AGENT_NAME},
    {"label": "Reportes", "route_hint": REPORTS_AGENT_NAME},
]


def _looks_like_menu_request(message: str) -> bool:
    ml = message.strip().lower()
    return any(cue == ml or ml.startswith(cue + " ") for cue in _MENU_CUES)


def _looks_like_ambiguous_query(message: str) -> bool:
    ml = message.strip().lower()
    return any(cue == ml for cue in _AMBIGUOUS_CUES)


def _build_route_menu() -> tuple[str, list[dict[str, Any]]]:
    actions = [
        {
            "id": f"route_{cat['route_hint']}",
            "label": cat["label"],
            "kind": "send_message",
            "message": f"Quiero consultar sobre {cat['label'].lower()}.",
            "route_hint": cat["route_hint"],
            "selection_behavior": "route_and_resend",
            "style": "secondary",
        }
        for cat in _DOMAIN_CATEGORIES
    ]
    reply = "¿Sobre qué área del proyecto querés consultar?"
    blocks: list[dict[str, Any]] = [
        build_text_block(reply),
        {"type": "actions", "actions": actions},
    ]
    return reply, blocks


def _build_route_clarification() -> tuple[str, list[dict[str, Any]]]:
    actions = [
        {
            "id": f"clarify_{cat['route_hint']}",
            "label": cat["label"],
            "kind": "send_message",
            "message": f"Quiero consultar sobre {cat['label'].lower()}.",
            "route_hint": cat["route_hint"],
            "selection_behavior": "prompt_for_query",
            "style": "secondary",
        }
        for cat in _DOMAIN_CATEGORIES
    ]
    reply = "Necesito un poco más de contexto. ¿Sobre qué área querés consultar?"
    blocks: list[dict[str, Any]] = [
        build_text_block(reply),
        {"type": "actions", "actions": actions},
    ]
    return reply, blocks


def _build_turn_context(
    *,
    message: str,
    route_hint: str | None,
    chat_context: dict[str, Any] | None,
    dossier: dict[str, Any] | None,
) -> "TurnContext":
    from src.routing.context import TurnContext

    normalized_hint = _normalize_explicit_route_hint(route_hint)
    is_insight_handoff = isinstance(chat_context, dict) and any(
        str(chat_context.get(k) or "").strip() for k in ("notification_id", "insight_id")
    )

    return TurnContext(
        message=message,
        route_hint=normalized_hint,
        route_hint_source="explicit" if normalized_hint else None,
        handoff=chat_context if is_insight_handoff else None,
        is_menu_request=_looks_like_menu_request(message),
        is_ambiguous_query=_looks_like_ambiguous_query(message),
        handoff_is_structured_insight=is_insight_handoff,
        handoff_is_valid=is_insight_handoff,
        legacy_insight_match=_looks_like_insight_chat_request(message.lower(), chat_context),
    )


def _build_workspace_context_block(workspace: dict[str, Any] | None) -> str:
    """Arma un bloque de contexto legible con la selección activa del usuario."""
    if not workspace:
        return ""
    pairs: list[str] = []
    mapping = [
        ("Cliente", "customer_name", "customer_id"),
        ("Proyecto", "project_name", "project_id"),
        ("Campaña", "campaign_name", "campaign_id"),
        ("Campo", "field_name", "field_id"),
    ]
    for label, name_key, id_key in mapping:
        name = workspace.get(name_key)
        ident = workspace.get(id_key)
        if not name and ident in (None, ""):
            continue
        text = str(name) if name else ""
        if ident not in (None, ""):
            text = f"{text} (id={ident})" if text else f"id={ident}"
        pairs.append(f"- {label}: {text}")
    if not pairs:
        return ""
    header = (
        "Selección activa del usuario en la UI. Usala para acotar resultados "
        "sin volver a preguntarle; si cambia entre turnos, adaptá la respuesta al nuevo contexto."
    )
    return header + "\n" + "\n".join(pairs)


async def run_ponti_chat_turn(
    *,
    request_id: str,
    project_id: str,
    user_id: str,
    message: str,
    chat_id: str | None,
    route_hint: str | None,
    chat_context: dict[str, Any] | None,
    preferred_language: str | None,
    accept_language: str | None,
    settings: Settings,
    llm: LLMProvider,
    get_summary,
    repo: AIRepository,
    workspace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lang = _resolve_language(preferred_language, accept_language)
    clean = message.strip()
    if not clean:
        return {
            "request_id": request_id,
            "output_kind": OUTPUT_KIND_CHAT_REPLY,
            "content_language": lang,
            "chat_id": chat_id or "",
            "reply": "Escribí un mensaje para continuar.",
            "tokens_used": 0,
            "tool_calls": [],
            "pending_confirmations": [],
            "blocks": [build_text_block("Escribí un mensaje para continuar.")],
            "routed_agent": "general",
            "routing_source": ROUTING_SOURCE_ORCHESTRATOR,
        }

    from src.routing.resolve import resolve_routing_decision

    # --- Fase 5: pipeline de routing unificado ---
    turn_context = _build_turn_context(
        message=clean, route_hint=route_hint, chat_context=chat_context, dossier=None,
    )
    decision = await resolve_routing_decision(turn_context)

    _handoff = turn_context.handoff
    logger.info(
        "ponti_turn_routing_decision",
        request_id=request_id,
        project_id=project_id,
        handler_kind=decision.handler_kind,
        routing_target=decision.target,
        routing_reason=decision.reason,
        route_hint=route_hint or "",
        route_hint_source=turn_context.route_hint_source or "",
        handoff_source=str((_handoff or {}).get("source", "")) if _handoff else "",
        handoff_scope=str((_handoff or {}).get("insight_scope", "")) if _handoff else "",
        handoff_valid=turn_context.handoff_is_valid,
    )

    # Respuestas estáticas (menú / clarificación)
    if decision.handler_kind == "static_reply":
        if decision.target == "route_menu":
            reply, blocks = _build_route_menu()
        else:
            reply, blocks = _build_route_clarification()
        return {
            "request_id": request_id,
            "output_kind": OUTPUT_KIND_CHAT_REPLY,
            "content_language": lang,
            "chat_id": chat_id or "",
            "reply": reply,
            "tokens_used": 0,
            "tool_calls": [],
            "pending_confirmations": [],
            "blocks": blocks,
            "routed_agent": PRODUCT_AGENT_NAME,
            "routing_source": ROUTING_SOURCE_ORCHESTRATOR,
        }

    routed = decision.target if decision.handler_kind == "direct_agent" else (
        INSIGHT_CHAT_AGENT_NAME if decision.handler_kind == "insight_lane" else PRODUCT_AGENT_NAME
    )
    routing_source = (
        ROUTING_SOURCE_INSIGHT_CHAT_AGENT if decision.handler_kind == "insight_lane"
        else ROUTING_SOURCE_UI_HINT if decision.handler_kind == "direct_agent"
        else ROUTING_SOURCE_ORCHESTRATOR
    )
    # Fallback: si el pipeline no mapeó, usa _resolve_route como antes
    if decision.handler_kind == "orchestrator":
        routed, routing_source = _resolve_route(route_hint, clean, chat_context=chat_context, dossier=None)

    row = None
    if chat_id:
        row = await asyncio.to_thread(repo.get_conversation, project_id, chat_id)
        if row is None or row.user_id != user_id:
            raise ValueError("conversation_not_found")

    if row is None:
        row = await asyncio.to_thread(
            lambda: repo.create_conversation(project_id=project_id, user_id=user_id, title=clean[:60]),
        )

    backend = PontiBackendClient(settings)
    backend_ok = backend.is_configured()
    dossier_row = await asyncio.to_thread(repo.get_or_create_dossier, project_id)
    dossier = dict(dossier_row.dossier or {})
    sync_chat_handoff(dossier, route_hint=route_hint, chat_context=chat_context, content_language=lang)
    # Re-resolve con dossier para carry-forward
    if decision.handler_kind == "orchestrator":
        routed, routing_source = _resolve_route(route_hint, clean, chat_context=chat_context, dossier=dossier)
    dossier = await _refresh_project_dossier(
        dossier=dossier,
        project_id=project_id,
        user_id=user_id,
        routed=routed,
        user_message=clean,
        settings=settings,
        backend=backend,
        get_summary=get_summary,
    )
    context_block = build_project_operating_context_for_prompt(dossier, user_id)
    system = base_system_prompt(settings.domain, backend_tools=backend_ok) + "\n" + route_system_addon(routed)
    workspace_block = _build_workspace_context_block(workspace)
    if workspace_block:
        system += f"\n\n{workspace_block}"
    if context_block:
        system += f"\n\nContexto operativo del proyecto:\n{context_block}"
    if lang == "en":
        system += "\nThe user prefers English for this turn."

    history = _history_to_messages(row.messages)

    # --- Fase 6: inyectar evidencia de insight previo para follow-ups ---
    _prior_evidence = extract_insight_evidence(list(row.messages))
    if _prior_evidence is not None:
        _compacted = compact_insight_evidence_for_prompt(_prior_evidence)
        history = [
            Message(
                role="system",
                content=(
                    "CONTEXTO INSIGHT PREVIO (datos reales del proyecto, "
                    "usá solo estos números para responder follow-ups):\n"
                    f"{_compacted}"
                ),
            ),
            *history,
        ]
        logger.info(
            "insight_evidence_injected",
            request_id=request_id,
            project_id=project_id,
            conversation_id=row.id,
            scope=_prior_evidence.get("scope", ""),
            period=_prior_evidence.get("period", ""),
        )

    declarations = build_ponti_tool_declarations(backend_configured=backend_ok)
    tool_handlers = build_ponti_tool_handlers(get_summary=get_summary, backend=backend if backend_ok else None)

    payload_messages: list[Message] = [
        Message(role="system", content=system),
        *history,
        Message(role="user", content=clean),
    ]
    limits = _orchestrator_limits(settings)

    assistant_parts: list[str] = []
    tool_names: list[str] = []
    tokens_in = estimate_tokens("\n".join(m.content for m in payload_messages))

    try:
        async for chunk in orchestrate(llm, payload_messages, declarations, tool_handlers, context={"project_id": project_id, "user_id": user_id}, limits=limits):
            if chunk.type == "text" and chunk.text:
                assistant_parts.append(chunk.text)
            if chunk.type == "tool_call" and chunk.tool_call and chunk.tool_call.name:
                tool_names.append(chunk.tool_call.name.strip())
    except Exception:
        logger.exception("ponti_chat_turn_failed", extra={"request_id": request_id, "project_id": project_id})
        assistant_parts = ["No pude completar la solicitud en este momento. Reintentá en unos segundos o verificá la configuración del modelo."]
        tool_names = []

    assistant_text = "".join(assistant_parts).strip() or "No pude generar una respuesta en este momento."
    tokens_out = estimate_tokens(assistant_text)
    now_iso = datetime.now(UTC).isoformat()

    user_msg: dict[str, Any] = {"role": "user", "content": clean, "ts": now_iso}
    if chat_context:
        user_msg["chat_context"] = chat_context
    # Insight-evidence injection desde DB local quedó deprecada cuando los
    # insights se movieron a ponti-backend. La UI hoy manda el contenido del
    # insight inline en el primer mensaje del chat, sin pasar insight_id.
    insight_evidence_payload: dict[str, Any] | None = None

    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
        "ts": now_iso,
        "tool_calls": sorted(set(tool_names)),
        "routed_agent": normalize_routed_agent(routed),
        "routing_source": normalize_routing_source(routing_source),
    }
    if insight_evidence_payload is not None:
        assistant_msg["insight_evidence"] = insight_evidence_payload

    capture_turn_memory(
        dossier,
        user_id=user_id,
        user_message=clean,
        assistant_reply=assistant_text,
        routed_agent=routed,
        route_hint=route_hint,
        chat_context=chat_context,
        content_language=lang,
        tool_calls=sorted(set(tool_names)),
        pending_confirmations=[],
        confirmed_actions=set(),
    )

    await asyncio.to_thread(
        repo.append_messages,
        project_id=project_id,
        conversation_id=row.id,
        new_messages=[user_msg, assistant_msg],
        extra_tool_calls=len(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )
    await asyncio.to_thread(repo.save_dossier, project_id, dossier)

    await record_agent_event(
        repo,
        project_id=project_id,
        conversation_id=row.id,
        agent_mode=routed,
        channel="chat",
        actor_id=user_id,
        actor_type="user",
        action="chat_turn",
        result="success",
        confirmed=True,
        request_id=request_id,
        metadata={
            "routing_source": routing_source,
            "routing_reason": decision.reason,
            "handler_kind": decision.handler_kind,
            "tool_calls": sorted(set(tool_names)),
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "has_handoff": chat_context is not None,
            "evidence_injected": _prior_evidence is not None,
        },
    )

    logger.info(
        "ponti_turn_summary",
        request_id=request_id,
        project_id=project_id,
        chat_id=row.id,
        routed_agent=routed,
        routing_source=routing_source,
        routing_reason=decision.reason,
        handler_kind=decision.handler_kind,
        has_handoff=chat_context is not None,
        handoff_scope=str((chat_context or {}).get("insight_scope", "")) if chat_context else "",
        evidence_injected=_prior_evidence is not None,
        tool_calls_count=len(set(tool_names)),
        tool_calls=sorted(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        result="success",
    )

    return {
        "request_id": request_id,
        "output_kind": OUTPUT_KIND_CHAT_REPLY,
        "content_language": lang,
        "chat_id": row.id,
        "reply": assistant_text,
        "tokens_used": int(tokens_in + tokens_out),
        "tool_calls": sorted(set(tool_names)),
        "pending_confirmations": [],
        "blocks": [build_text_block(assistant_text)],
        "routed_agent": routed,
        "routing_source": routing_source,
    }


async def iter_ponti_chat_sse(
    *,
    request_id: str,
    project_id: str,
    user_id: str,
    message: str,
    chat_id: str | None,
    route_hint: str | None,
    chat_context: dict[str, Any] | None,
    preferred_language: str | None,
    accept_language: str | None,
    settings: Settings,
    llm: LLMProvider,
    get_summary,
    repo: AIRepository,
    workspace: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, str]]:
    """Misma lógica que run_ponti_chat_turn pero emite SSE.

    Aplica el routing pipeline (Fase 5), inyección de evidencia (Fase 6),
    logs operativos (Fase 9) y audit event para mantener paridad con el
    endpoint JSON. Es la ruta usada en producción por el frontend.
    """
    from src.routing.resolve import resolve_routing_decision

    lang = _resolve_language(preferred_language, accept_language)
    clean = message.strip()
    if not clean:
        yield to_sse_event("error", {"message": "empty_message"})
        return

    # --- Fase 5: pipeline de routing unificado ---
    turn_context = _build_turn_context(
        message=clean, route_hint=route_hint, chat_context=chat_context, dossier=None,
    )
    decision = await resolve_routing_decision(turn_context)

    _handoff = turn_context.handoff
    logger.info(
        "ponti_turn_routing_decision",
        request_id=request_id,
        project_id=project_id,
        handler_kind=decision.handler_kind,
        routing_target=decision.target,
        routing_reason=decision.reason,
        route_hint=route_hint or "",
        route_hint_source=turn_context.route_hint_source or "",
        handoff_source=str((_handoff or {}).get("source", "")) if _handoff else "",
        handoff_scope=str((_handoff or {}).get("insight_scope", "")) if _handoff else "",
        handoff_valid=turn_context.handoff_is_valid,
    )

    # Respuestas estáticas (menú / clarificación) — emitir como single-shot SSE
    if decision.handler_kind == "static_reply":
        if decision.target == "route_menu":
            reply, blocks = _build_route_menu()
        else:
            reply, blocks = _build_route_clarification()
        # No tenemos chat_id todavía: asegurar que existe la conversación
        row = None
        if chat_id:
            row = await asyncio.to_thread(repo.get_conversation, project_id, chat_id)
            if row is None or row.user_id != user_id:
                yield to_sse_event("error", {"message": "conversation_not_found"})
                return
        if row is None:
            row = await asyncio.to_thread(
                lambda: repo.create_conversation(project_id=project_id, user_id=user_id, title=clean[:60]),
            )
        yield to_sse_event("start", {
            "request_id": request_id,
            "chat_id": row.id,
            "routed_agent": PRODUCT_AGENT_NAME,
            "routing_source": ROUTING_SOURCE_ORCHESTRATOR,
        })
        yield to_sse_event("text", {"content": reply})
        yield to_sse_event("done", {
            "request_id": request_id,
            "chat_id": row.id,
            "reply": reply,
            "tokens_used": 0,
            "tool_calls": [],
            "content_language": lang,
            "routed_agent": PRODUCT_AGENT_NAME,
            "routing_source": ROUTING_SOURCE_ORCHESTRATOR,
            "blocks_json": json.dumps(blocks, ensure_ascii=False),
        })
        return

    routed = decision.target if decision.handler_kind == "direct_agent" else (
        INSIGHT_CHAT_AGENT_NAME if decision.handler_kind == "insight_lane" else PRODUCT_AGENT_NAME
    )
    routing_source = (
        ROUTING_SOURCE_INSIGHT_CHAT_AGENT if decision.handler_kind == "insight_lane"
        else ROUTING_SOURCE_UI_HINT if decision.handler_kind == "direct_agent"
        else ROUTING_SOURCE_ORCHESTRATOR
    )
    if decision.handler_kind == "orchestrator":
        routed, routing_source = _resolve_route(route_hint, clean, chat_context=chat_context, dossier=None)

    row = None
    if chat_id:
        row = await asyncio.to_thread(repo.get_conversation, project_id, chat_id)
        if row is None or row.user_id != user_id:
            yield to_sse_event("error", {"message": "conversation_not_found"})
            return

    if row is None:
        row = await asyncio.to_thread(
            lambda: repo.create_conversation(project_id=project_id, user_id=user_id, title=clean[:60]),
        )

    backend = PontiBackendClient(settings)
    backend_ok = backend.is_configured()
    dossier_row = await asyncio.to_thread(repo.get_or_create_dossier, project_id)
    dossier = dict(dossier_row.dossier or {})
    sync_chat_handoff(dossier, route_hint=route_hint, chat_context=chat_context, content_language=lang)
    if decision.handler_kind == "orchestrator":
        routed, routing_source = _resolve_route(route_hint, clean, chat_context=chat_context, dossier=dossier)
    dossier = await _refresh_project_dossier(
        dossier=dossier,
        project_id=project_id,
        user_id=user_id,
        routed=routed,
        user_message=clean,
        settings=settings,
        backend=backend,
        get_summary=get_summary,
    )
    context_block = build_project_operating_context_for_prompt(dossier, user_id)
    system = base_system_prompt(settings.domain, backend_tools=backend_ok) + "\n" + route_system_addon(routed)
    workspace_block = _build_workspace_context_block(workspace)
    if workspace_block:
        system += f"\n\n{workspace_block}"
    if context_block:
        system += f"\n\nContexto operativo del proyecto:\n{context_block}"
    if lang == "en":
        system += "\nThe user prefers English for this turn."

    history = _history_to_messages(row.messages)

    # --- Fase 6: inyectar evidencia de insight previo para follow-ups ---
    _prior_evidence = extract_insight_evidence(list(row.messages))
    if _prior_evidence is not None:
        _compacted = compact_insight_evidence_for_prompt(_prior_evidence)
        history = [
            Message(
                role="system",
                content=(
                    "CONTEXTO INSIGHT PREVIO (datos reales del proyecto, "
                    "usá solo estos números para responder follow-ups):\n"
                    f"{_compacted}"
                ),
            ),
            *history,
        ]
        logger.info(
            "insight_evidence_injected",
            request_id=request_id,
            project_id=project_id,
            conversation_id=row.id,
            scope=_prior_evidence.get("scope", ""),
            period=_prior_evidence.get("period", ""),
        )

    declarations = build_ponti_tool_declarations(backend_configured=backend_ok)
    tool_handlers = build_ponti_tool_handlers(get_summary=get_summary, backend=backend if backend_ok else None)

    payload_messages: list[Message] = [
        Message(role="system", content=system),
        *history,
        Message(role="user", content=clean),
    ]
    limits = _orchestrator_limits(settings)
    tokens_in = estimate_tokens("\n".join(m.content for m in payload_messages))

    assistant_parts: list[str] = []
    tool_names: list[str] = []

    yield to_sse_event("start", {
        "request_id": request_id,
        "chat_id": row.id,
        "routed_agent": normalize_routed_agent(routed),
        "routing_source": normalize_routing_source(routing_source),
    })

    try:
        async for chunk in orchestrate(llm, payload_messages, declarations, tool_handlers, context={"project_id": project_id, "user_id": user_id}, limits=limits):
            if chunk.type == "text" and chunk.text:
                assistant_parts.append(chunk.text)
                yield to_sse_event("text", {"content": chunk.text})
            elif chunk.type == "tool_call" and chunk.tool_call and chunk.tool_call.name:
                name = chunk.tool_call.name.strip()
                tool_names.append(name)
                yield to_sse_event("tool_call", {"tool": name, "status": "running"})
            elif chunk.type == "tool_result" and chunk.tool_call:
                name = str(chunk.tool_call.name).strip()
                yield to_sse_event("tool_result", {"tool": name, "status": "done"})
    except Exception as exc:
        yield to_sse_event("error", {"message": "stream_failed", "detail": str(exc)})
        return

    assistant_text = "".join(assistant_parts).strip() or "No pude generar una respuesta en este momento."
    tokens_out = estimate_tokens(assistant_text)
    now_iso = datetime.now(UTC).isoformat()

    user_msg: dict[str, Any] = {"role": "user", "content": clean, "ts": now_iso}
    if chat_context:
        user_msg["chat_context"] = chat_context

    insight_evidence_payload: dict[str, Any] | None = None

    assistant_msg: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
        "ts": now_iso,
        "tool_calls": sorted(set(tool_names)),
        "routed_agent": normalize_routed_agent(routed),
        "routing_source": normalize_routing_source(routing_source),
    }
    if insight_evidence_payload is not None:
        assistant_msg["insight_evidence"] = insight_evidence_payload

    capture_turn_memory(
        dossier,
        user_id=user_id,
        user_message=clean,
        assistant_reply=assistant_text,
        routed_agent=routed,
        route_hint=route_hint,
        chat_context=chat_context,
        content_language=lang,
        tool_calls=sorted(set(tool_names)),
        pending_confirmations=[],
        confirmed_actions=set(),
    )

    await asyncio.to_thread(
        repo.append_messages,
        project_id=project_id,
        conversation_id=row.id,
        new_messages=[user_msg, assistant_msg],
        extra_tool_calls=len(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )
    await asyncio.to_thread(repo.save_dossier, project_id, dossier)

    await record_agent_event(
        repo,
        project_id=project_id,
        conversation_id=row.id,
        agent_mode=routed,
        channel="chat_stream",
        actor_id=user_id,
        actor_type="user",
        action="chat_turn",
        result="success",
        confirmed=True,
        request_id=request_id,
        metadata={
            "routing_source": routing_source,
            "routing_reason": decision.reason,
            "handler_kind": decision.handler_kind,
            "tool_calls": sorted(set(tool_names)),
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "has_handoff": chat_context is not None,
            "evidence_injected": _prior_evidence is not None,
        },
    )

    logger.info(
        "ponti_turn_summary",
        request_id=request_id,
        project_id=project_id,
        chat_id=row.id,
        routed_agent=routed,
        routing_source=routing_source,
        routing_reason=decision.reason,
        handler_kind=decision.handler_kind,
        has_handoff=chat_context is not None,
        handoff_scope=str((chat_context or {}).get("insight_scope", "")) if chat_context else "",
        evidence_injected=_prior_evidence is not None,
        tool_calls_count=len(set(tool_names)),
        tool_calls=sorted(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        result="success",
    )

    yield to_sse_event("done", {
        "request_id": request_id,
        "chat_id": row.id,
        "reply": assistant_text,
        "tokens_used": int(tokens_in + tokens_out),
        "tool_calls": sorted(set(tool_names)),
        "content_language": lang,
        "routed_agent": normalize_routed_agent(routed),
        "routing_source": normalize_routing_source(routing_source),
        "blocks_json": json.dumps([build_text_block(assistant_text)], ensure_ascii=False),
    })
