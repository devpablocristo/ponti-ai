"""Un turno de chat asistente Ponti: orquestación LLM + tools (insights + ponti-backend) + persistencia."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Literal

from runtime import OUTPUT_KIND_CHAT_REPLY, ROUTING_SOURCE_ORCHESTRATOR, ROUTING_SOURCE_UI_HINT
from runtime.api.events import to_sse_event
from runtime.chat.blocks import build_text_block
from runtime.domain.models import LLMProvider, Message
from runtime.orchestrator import OrchestratorLimits, orchestrate
from runtime.text import estimate_tokens

from adapters.outbound.db.repos.project_dossier_repo_pg import ProjectDossierRepositoryPG
from adapters.outbound.http.ponti_backend_client import PontiBackendClient
from app.config import Settings
from contexts.chat.application.project_dossier import (
    build_project_operating_context_for_prompt,
    capture_turn_memory,
    sync_dashboard_snapshot,
    sync_insights_snapshot,
    sync_project_from_backend,
)
from contexts.chat.application.ponti_tools import build_ponti_tool_declarations, build_ponti_tool_handlers
from adapters.outbound.db.repos.conversation_repo_pg import ConversationRepositoryPG
from contexts.insights.application.use_cases.get_summary import GetSummary

PontiRoutedAgent = Literal[
    "general",
    "dashboard",
    "labors",
    "supplies",
    "campaigns",
    "lots",
    "stock",
    "reports",
    "copilot",
]

_VALID_AGENTS = frozenset(
    {
        "general",
        "dashboard",
        "labors",
        "supplies",
        "campaigns",
        "lots",
        "stock",
        "reports",
        "copilot",
    }
)

_EXECUTIVE_CUES: tuple[str, ...] = (
    "cómo viene",
    "como viene",
    "mirada de dueño",
    "mirada de dueno",
    "resumen ejecutivo",
    "salud del proyecto",
    "estado del proyecto",
    "qué harías",
    "que harias",
    "qué conviene",
    "que conviene",
    "prioridades",
    "riesgos",
    "acciones concretas",
    "plan de acción",
    "plan de accion",
    "desvío",
    "desvio",
    "resultado operativo",
)


def _normalize_agent(raw: str | None) -> PontiRoutedAgent:
    if not raw:
        return "general"
    key = str(raw).strip().lower()
    if key in _VALID_AGENTS:
        return key  # type: ignore[return-value]
    return "general"


def _resolve_route(route_hint: str | None, message: str) -> tuple[PontiRoutedAgent, str]:
    ml = message.lower()
    if route_hint:
        hinted = _normalize_agent(route_hint)
        if _looks_executive_request(ml) and hinted in {"general", "supplies", "labors", "campaigns", "lots", "stock"}:
            return "dashboard", ROUTING_SOURCE_ORCHESTRATOR
        return hinted, ROUTING_SOURCE_UI_HINT
    if _looks_executive_request(ml):
        return "dashboard", ROUTING_SOURCE_ORCHESTRATOR
    if any(k in ml for k in ("insight", "resumen", "panorama", "alerta", "métrica", "metrica", "dashboard")):
        return "dashboard", ROUTING_SOURCE_ORCHESTRATOR
    if any(k in ml for k in ("labor", "laboreo", "jornal", "contratista")):
        return "labors", ROUTING_SOURCE_ORCHESTRATOR
    if any(k in ml for k in ("insumo", "insumos", "abastecimiento")):
        return "supplies", ROUTING_SOURCE_ORCHESTRATOR
    if "campaña" in ml or "campana" in ml:
        return "campaigns", ROUTING_SOURCE_ORCHESTRATOR
    if "lote" in ml:
        return "lots", ROUTING_SOURCE_ORCHESTRATOR
    if any(k in ml for k in ("stock", "existencia", "inventario")):
        return "stock", ROUTING_SOURCE_ORCHESTRATOR
    if any(k in ml for k in ("informe", "reporte", "export")):
        return "reports", ROUTING_SOURCE_ORCHESTRATOR
    return "general", ROUTING_SOURCE_ORCHESTRATOR


def _looks_executive_request(message: str) -> bool:
    return any(cue in message for cue in _EXECUTIVE_CUES)


def _route_system_addon(agent: PontiRoutedAgent) -> str:
    addons: dict[PontiRoutedAgent, str] = {
        "general": "Ámbito asesor de proyecto: priorizá salud operativa, riesgos y decisiones; usá tools para datos concretos.",
        "dashboard": "Ámbito tablero/insights: sintetizá salud ejecutiva, desvíos y prioridades usando get_insights_summary y fetch_dashboard.",
        "labors": "Ámbito labores: fetch_labors_catalog, fetch_labors_grouped, fetch_labor_metrics.",
        "supplies": "Ámbito insumos: fetch_supplies, fetch_supply_detail, fetch_supply_movements.",
        "campaigns": "Ámbito campañas: fetch_campaigns.",
        "lots": "Ámbito lotes: fetch_lots, fetch_lot_detail, fetch_lot_metrics.",
        "stock": "Ámbito stock: fetch_stock_summary, fetch_stock_periods.",
        "reports": "Ámbito informes: fetch_report_* según el pedido.",
        "copilot": "Handoff copilot: get_insights_summary y datos vía tools.",
    }
    return addons.get(agent, addons["general"])


def _base_system_prompt(domain: str, *, backend_tools: bool) -> str:
    d = (domain or "agriculture").strip()
    tools_line = (
        "Tenés get_insights_summary (insights) y herramientas fetch_* que leen ponti-backend (solo lectura) "
        "cuando PONTI_BACKEND_* está configurado."
        if backend_tools
        else "Tenés get_insights_summary; configurá PONTI_BACKEND_BASE_URL y PONTI_BACKEND_API_KEY para datos de labores, insumos, lotes, OT, etc."
    )
    return f"""Sos el asesor operativo de Ponti, plataforma de gestión agrícola (dominio: {d}).
Respondé en el idioma que indique el usuario (español por defecto).
{tools_line}
No inventes números ni registros: obtenelos con tools.
Priorizá claridad ejecutiva, criterio operativo y acciones concretas antes que enumerar catálogos.
No uses markdown pesado; texto claro y conciso."""


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


async def _refresh_project_dossier(
    *,
    dossier: dict[str, Any],
    project_id: str,
    user_id: str,
    routed: PontiRoutedAgent,
    user_message: str,
    settings: Settings,
    backend: PontiBackendClient,
    get_summary: GetSummary,
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
        routed in {"dashboard", "reports", "stock", "lots", "copilot"} or _looks_executive_request(user_message.lower())
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


def _compact(value: Any) -> str:
    return str(value or "").strip()


async def run_ponti_chat_turn(
    *,
    request_id: str,
    project_id: str,
    user_id: str,
    message: str,
    chat_id: str | None,
    route_hint: str | None,
    preferred_language: str | None,
    accept_language: str | None,
    settings: Settings,
    llm: LLMProvider,
    get_summary: GetSummary,
    repo: ConversationRepositoryPG,
    dossier_repo: ProjectDossierRepositoryPG,
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

    routed, routing_source = _resolve_route(route_hint, clean)

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
    dossier_row = await asyncio.to_thread(dossier_repo.get_or_create, project_id)
    dossier = dict(dossier_row.dossier or {})
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
    system = (
        _base_system_prompt(settings.domain, backend_tools=backend_ok)
        + "\n"
        + _route_system_addon(routed)
    )
    if context_block:
        system += f"\n\nContexto operativo del proyecto:\n{context_block}"
    if lang == "en":
        system += "\nThe user prefers English for this turn."

    history = _history_to_messages(row.messages)
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
        async for chunk in orchestrate(
            llm,
            payload_messages,
            declarations,
            tool_handlers,
            context={"project_id": project_id, "user_id": user_id},
            limits=limits,
        ):
            if chunk.type == "text" and chunk.text:
                assistant_parts.append(chunk.text)
            if chunk.type == "tool_call" and chunk.tool_call and chunk.tool_call.name:
                tool_names.append(chunk.tool_call.name.strip())
    except Exception:
        assistant_parts = [
            "No pude completar la solicitud en este momento. Reintentá en unos segundos o verificá la configuración del modelo."
        ]
        tool_names = []

    assistant_text = "".join(assistant_parts).strip()
    if not assistant_text:
        assistant_text = "No pude generar una respuesta en este momento."

    tokens_out = estimate_tokens(assistant_text)
    now_iso = datetime.now(UTC).isoformat()

    user_message: dict[str, Any] = {"role": "user", "content": clean, "ts": now_iso}
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
        "ts": now_iso,
        "tool_calls": sorted(set(tool_names)),
    }

    capture_turn_memory(
        dossier,
        user_id=user_id,
        user_message=clean,
        assistant_reply=assistant_text,
        routed_agent=routed,
        tool_calls=sorted(set(tool_names)),
        pending_confirmations=[],
        confirmed_actions=set(),
    )

    await asyncio.to_thread(
        repo.append_messages,
        project_id=project_id,
        conversation_id=row.id,
        new_messages=[user_message, assistant_message],
        extra_tool_calls=len(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )
    await asyncio.to_thread(dossier_repo.save, project_id, dossier)

    blocks: list[dict[str, Any]] = [build_text_block(assistant_text)]

    return {
        "request_id": request_id,
        "output_kind": OUTPUT_KIND_CHAT_REPLY,
        "content_language": lang,
        "chat_id": row.id,
        "reply": assistant_text,
        "tokens_used": int(tokens_in + tokens_out),
        "tool_calls": sorted(set(tool_names)),
        "pending_confirmations": [],
        "blocks": blocks,
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
    preferred_language: str | None,
    accept_language: str | None,
    settings: Settings,
    llm: LLMProvider,
    get_summary: GetSummary,
    repo: ConversationRepositoryPG,
    dossier_repo: ProjectDossierRepositoryPG,
) -> AsyncIterator[dict[str, str]]:
    """Misma lógica que run_ponti_chat_turn pero emite SSE (text, tool_*, done)."""
    lang = _resolve_language(preferred_language, accept_language)
    clean = message.strip()
    if not clean:
        yield to_sse_event("error", {"message": "empty_message"})
        return

    routed, routing_source = _resolve_route(route_hint, clean)

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
    dossier_row = await asyncio.to_thread(dossier_repo.get_or_create, project_id)
    dossier = dict(dossier_row.dossier or {})
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
    system = (
        _base_system_prompt(settings.domain, backend_tools=backend_ok)
        + "\n"
        + _route_system_addon(routed)
    )
    if context_block:
        system += f"\n\nContexto operativo del proyecto:\n{context_block}"
    if lang == "en":
        system += "\nThe user prefers English for this turn."

    history = _history_to_messages(row.messages)
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

    yield to_sse_event(
        "start",
        {"request_id": request_id, "chat_id": row.id, "routed_agent": routed, "routing_source": routing_source},
    )

    try:
        async for chunk in orchestrate(
            llm,
            payload_messages,
            declarations,
            tool_handlers,
            context={"project_id": project_id, "user_id": user_id},
            limits=limits,
        ):
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
    except Exception as exc:  # noqa: BLE001
        yield to_sse_event("error", {"message": "stream_failed", "detail": str(exc)})
        return

    assistant_text = "".join(assistant_parts).strip() or "No pude generar una respuesta en este momento."
    tokens_out = estimate_tokens(assistant_text)
    now_iso = datetime.now(UTC).isoformat()

    user_message: dict[str, Any] = {"role": "user", "content": clean, "ts": now_iso}
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
        "ts": now_iso,
        "tool_calls": sorted(set(tool_names)),
    }

    capture_turn_memory(
        dossier,
        user_id=user_id,
        user_message=clean,
        assistant_reply=assistant_text,
        routed_agent=routed,
        tool_calls=sorted(set(tool_names)),
        pending_confirmations=[],
        confirmed_actions=set(),
    )

    await asyncio.to_thread(
        repo.append_messages,
        project_id=project_id,
        conversation_id=row.id,
        new_messages=[user_message, assistant_message],
        extra_tool_calls=len(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )
    await asyncio.to_thread(dossier_repo.save, project_id, dossier)

    yield to_sse_event(
        "done",
        {
            "request_id": request_id,
            "chat_id": row.id,
            "reply": assistant_text,
            "tokens_used": int(tokens_in + tokens_out),
            "tool_calls": sorted(set(tool_names)),
            "content_language": lang,
            "routed_agent": routed,
            "routing_source": routing_source,
            "blocks_json": json.dumps([build_text_block(assistant_text)], ensure_ascii=False),
        },
    )
