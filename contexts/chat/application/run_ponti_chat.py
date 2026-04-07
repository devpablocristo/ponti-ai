"""Un turno de chat asistente Ponti: orquestación LLM + herramienta de insights + persistencia."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any, Literal

from runtime import OUTPUT_KIND_CHAT_REPLY, ROUTING_SOURCE_ORCHESTRATOR, ROUTING_SOURCE_UI_HINT
from runtime.chat.blocks import build_text_block
from runtime.domain.models import LLMProvider, Message, ToolDeclaration
from runtime.orchestrator import OrchestratorLimits, orchestrate
from runtime.text import estimate_tokens

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


def _normalize_agent(raw: str | None) -> PontiRoutedAgent:
    if not raw:
        return "general"
    key = str(raw).strip().lower()
    if key in _VALID_AGENTS:
        return key  # type: ignore[return-value]
    return "general"


def _resolve_route(route_hint: str | None, message: str) -> tuple[PontiRoutedAgent, str]:
    if route_hint:
        return _normalize_agent(route_hint), ROUTING_SOURCE_UI_HINT
    ml = message.lower()
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


def _route_system_addon(agent: PontiRoutedAgent) -> str:
    addons: dict[PontiRoutedAgent, str] = {
        "general": "Ámbito general: podés orientar sobre el uso de Ponti (gestión agrícola) y derivar al módulo correcto.",
        "dashboard": "Ámbito dashboard/insights: priorizá interpretar datos ya calculados; usá la herramienta get_insights_summary si necesitás cifras actuales.",
        "labors": "Ámbito labores: jornales, tareas de campo, costos de laboreo.",
        "supplies": "Ámbito insumos: productos, movimientos y órdenes de trabajo vinculadas.",
        "campaigns": "Ámbito campañas agrícolas y planificación por campaña.",
        "lots": "Ámbito lotes: superficie, cultivo, ubicación.",
        "stock": "Ámbito stock y existencias.",
        "reports": "Ámbito informes y exportaciones.",
        "copilot": "Ámbito copilot: explicaciones sobre insights puntuales (handoff desde UI).",
    }
    return addons.get(agent, addons["general"])


def _base_system_prompt(domain: str) -> str:
    d = (domain or "agriculture").strip()
    return f"""Sos el asistente de Ponti, plataforma de gestión agrícola (dominio: {d}).
Respondé en el idioma que indique el usuario (español por defecto).
No inventes datos operativos del proyecto: si necesitás números de insights, llamá a la herramienta get_insights_summary.
No uses markdown pesado; texto claro y conciso.
Los módulos principales son: tablero/insights, labores, insumos, campañas, lotes, stock, clientes, órdenes de trabajo e informes."""


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
    domain: str,
    llm: LLMProvider,
    get_summary: GetSummary,
    repo: ConversationRepositoryPG,
    llm_max_tool_calls: int,
    llm_timeout_ms: int,
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

    system = _base_system_prompt(domain) + "\n" + _route_system_addon(routed)
    if lang == "en":
        system += "\nThe user prefers English for this turn."

    history = _history_to_messages(row.messages)
    declarations = [
        ToolDeclaration(
            name="get_insights_summary",
            description=(
                "Returns current insights summary for this project: counts and top insight titles. "
                "Call when the user asks for alerts, executive summary, or project health."
            ),
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
        )
    ]

    async def handle_get_insights_summary(project_id: str, **_kw: Any) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            summary = get_summary.handle(project_id)
            tops = [
                {"id": i.id, "title": i.title, "severity": i.severity, "type": i.type}
                for i in summary.top_insights[:10]
            ]
            return {
                "new_count_total": summary.new_count_total,
                "new_count_high_severity": summary.new_count_high_severity,
                "top_insights": tops,
            }

        return await asyncio.to_thread(_run)

    tool_handlers: dict[str, Any] = {"get_insights_summary": handle_get_insights_summary}

    payload_messages: list[Message] = [
        Message(role="system", content=system),
        *history,
        Message(role="user", content=clean),
    ]

    limits = OrchestratorLimits(
        max_tool_calls=max(1, int(llm_max_tool_calls)),
        tool_timeout_seconds=max(5.0, float(llm_timeout_ms) / 1000.0),
        total_timeout_seconds=max(30.0, min(120.0, float(llm_timeout_ms) / 1000.0 * 15)),
    )

    assistant_parts: list[str] = []
    tool_names: list[str] = []
    tokens_in = estimate_tokens("\n".join(m.content for m in payload_messages))

    try:
        async for chunk in orchestrate(
            llm,
            payload_messages,
            declarations,
            tool_handlers,
            context={"project_id": project_id},
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

    await asyncio.to_thread(
        repo.append_messages,
        project_id=project_id,
        conversation_id=row.id,
        new_messages=[user_message, assistant_message],
        extra_tool_calls=len(set(tool_names)),
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )

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
