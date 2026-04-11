"""Contexto y memoria del asesor de proyecto de Ponti."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from runtime.memory import (
    build_operational_memory_view,
    capture_operational_turn,
    consolidate_operational_memory,
    ensure_operational_memory,
    normalize_memory_text,
)


_SOFTWARE_PLAYBOOK = [
    "Ponti es una plataforma de gestión agrícola centrada en proyectos, campañas, campos, lotes, labores, insumos, stock, órdenes de trabajo e informes.",
    "Si el usuario pide una mirada ejecutiva del proyecto, priorizá salud operativa, costos, stock, resultado operativo, riesgos y próximas decisiones antes que listar registros.",
    "Usá el contexto del proyecto y el workspace actual para no responder de forma genérica ni como catálogo.",
    "Solo bajá a módulos específicos como labores, insumos, lotes o stock cuando la consulta realmente lo pida.",
]

_AGRICULTURE_PLAYBOOK = [
    "Conectá campaña, superficie, lotes, labores, insumos y stock antes de sugerir acciones.",
    "Priorizá desvíos de costo, ejecución contra presupuesto, salud del stock, órdenes de trabajo y resultado operativo.",
    "Cuando falten datos, decilo explícitamente y apoyate en dashboard, project detail o insights antes de improvisar.",
]

_PROJECT_MEMORY_CUES: tuple[str, ...] = (
    "recordá que",
    "recorda que",
    "tené en cuenta",
    "tene en cuenta",
    "este proyecto",
    "en esta campaña",
    "nuestro campo",
    "nuestro lote",
    "el cliente",
    "trabajamos con",
    "siempre",
    "nunca",
    "preferimos",
)

_USER_PREFERENCE_RULES: tuple[tuple[str, str], ...] = (
    ("breve", "El usuario prefiere respuestas breves."),
    ("corto", "El usuario prefiere respuestas cortas."),
    ("sin tabla", "El usuario prefiere respuestas sin tablas."),
    ("con tabla", "El usuario prefiere tablas cuando aclaran el análisis."),
    ("paso a paso", "El usuario prefiere explicaciones paso a paso."),
    ("priorizá", "El usuario suele pedir priorización explícita."),
    ("prioriza", "El usuario suele pedir priorización explícita."),
)


def _compact_text(value: Any) -> str:
    return str(value or "").strip()


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _extract_project_memory_candidate(user_message: str) -> str:
    text = normalize_memory_text(user_message)
    lowered = text.lower()
    if len(text) < 12:
        return ""
    if any(cue in lowered for cue in _PROJECT_MEMORY_CUES):
        return text
    return ""


def _extract_user_preferences(user_message: str) -> list[str]:
    lowered = normalize_memory_text(user_message).lower()
    preferences: list[str] = []
    for needle, preference in _USER_PREFERENCE_RULES:
        if needle in lowered and preference not in preferences:
            preferences.append(preference)
    return preferences


def _append_recent_unique(items: list[str], value: str, *, limit: int = 6) -> None:
    clean = normalize_memory_text(value, limit=120)
    if not clean:
        return
    if clean in items:
        items.remove(clean)
    items.append(clean)
    if len(items) > limit:
        del items[:-limit]


def sync_chat_handoff(
    dossier: dict[str, Any],
    *,
    route_hint: str | None,
    chat_context: dict[str, Any] | None,
    content_language: str | None,
) -> dict[str, Any]:
    workspace = dossier.setdefault("workspace", {})
    if route_hint:
        workspace["last_route_hint"] = normalize_memory_text(route_hint, limit=40)
        hints = workspace.setdefault("recent_route_hints", [])
        if isinstance(hints, list):
            _append_recent_unique(hints, route_hint, limit=8)
    if content_language:
        workspace["last_content_language"] = normalize_memory_text(content_language, limit=8)

    if not isinstance(chat_context, dict) or not chat_context:
        return dossier

    insight_chat_context = dossier.setdefault("insight_chat_context", {})
    legacy_context = dossier.pop("copilot_context", None)
    if isinstance(legacy_context, dict):
        for key, value in legacy_context.items():
            if key not in insight_chat_context or not _compact_text(insight_chat_context.get(key)):
                insight_chat_context[key] = value
    suggested = normalize_memory_text(chat_context.get("suggested_user_message"), limit=280)
    routed_agent = normalize_memory_text(chat_context.get("routed_agent") or route_hint, limit=40)
    source_kind = normalize_memory_text(chat_context.get("source_kind") or chat_context.get("kind"), limit=60)

    insight_chat_context["notification_id"] = normalize_memory_text(chat_context.get("notification_id"), limit=80)
    insight_chat_context["insight_id"] = normalize_memory_text(chat_context.get("insight_id"), limit=80)
    insight_chat_context["scope"] = normalize_memory_text(chat_context.get("scope"), limit=80)
    insight_chat_context["routed_agent"] = routed_agent
    insight_chat_context["content_language"] = normalize_memory_text(
        chat_context.get("content_language") or content_language,
        limit=8,
    )
    insight_chat_context["suggested_user_message"] = suggested
    insight_chat_context["source_kind"] = source_kind
    insight_chat_context["last_handoff_at"] = _iso_now()
    return dossier


def add_learned_context(dossier: dict[str, Any], fact: str) -> dict[str, Any]:
    learned = dossier.setdefault("learned_context", [])
    if fact not in learned:
        learned.append(fact)
    if len(learned) > 100:
        dossier["learned_context"] = learned[-100:]
    return dossier


def capture_turn_memory(
    dossier: dict[str, Any],
    *,
    user_id: str | None,
    user_message: str,
    assistant_reply: str,
    routed_agent: str,
    route_hint: str | None = None,
    chat_context: dict[str, Any] | None = None,
    content_language: str | None = None,
    tool_calls: list[str] | None = None,
    pending_confirmations: list[str] | None = None,
    confirmed_actions: set[str] | None = None,
) -> dict[str, Any]:
    business_facts: list[str] = []
    normalized = normalize_memory_text(user_message)
    if business_fact := _extract_project_memory_candidate(normalized):
        business_facts.append(business_fact)
        add_learned_context(dossier, business_fact)

    sync_chat_handoff(
        dossier,
        route_hint=route_hint or routed_agent,
        chat_context=chat_context,
        content_language=content_language,
    )

    capture_operational_turn(
        dossier,
        user_id=user_id,
        routed_agent=routed_agent,
        user_message=user_message,
        assistant_reply=assistant_reply,
        tool_calls=tool_calls,
        pending_confirmations=pending_confirmations,
        confirmed_actions=confirmed_actions,
        business_facts=business_facts,
        user_preferences=_extract_user_preferences(normalized),
    )
    return dossier


def sync_project_from_backend(dossier: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    project = dossier.setdefault("project", {})
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return dossier

    project["name"] = _compact_text(data.get("name")) or _compact_text(project.get("name"))
    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    campaign = data.get("campaign") if isinstance(data.get("campaign"), dict) else {}
    fields = data.get("fields") if isinstance(data.get("fields"), list) else []
    managers = data.get("managers") if isinstance(data.get("managers"), list) else []
    investors = data.get("investors") if isinstance(data.get("investors"), list) else []

    project["customer_name"] = _compact_text(customer.get("name")) or _compact_text(project.get("customer_name"))
    project["campaign_name"] = _compact_text(campaign.get("name")) or _compact_text(project.get("campaign_name"))
    project["fields"] = [
        {
            "name": _compact_text(field.get("name")),
            "lots": [
                {
                    "name": _compact_text(lot.get("name")),
                    "hectares": _compact_text(lot.get("hectares")),
                    "current_crop_name": _compact_text(lot.get("current_crop_name")),
                }
                for lot in field.get("lots", [])
                if isinstance(lot, dict)
            ],
        }
        for field in fields
        if isinstance(field, dict)
    ]
    project["managers"] = [_compact_text(item.get("name")) for item in managers if isinstance(item, dict) and _compact_text(item.get("name"))]
    project["investors"] = [_compact_text(item.get("name")) for item in investors if isinstance(item, dict) and _compact_text(item.get("name"))]

    hectares_total = 0.0
    for field in project["fields"]:
        for lot in field.get("lots", []):
            raw_hectares = _compact_text(lot.get("hectares"))
            try:
                hectares_total += float(raw_hectares)
            except ValueError:
                continue
    if hectares_total > 0:
        project["surface_hectares"] = round(hectares_total, 2)
    project["last_backend_refresh_at"] = _iso_now()
    return dossier


def sync_insights_snapshot(
    dossier: dict[str, Any],
    *,
    new_count_total: int,
    new_count_high_severity: int,
    top_titles: list[str],
) -> dict[str, Any]:
    snapshot = dossier.setdefault("insights_snapshot", {})
    snapshot["new_count_total"] = int(new_count_total)
    snapshot["new_count_high_severity"] = int(new_count_high_severity)
    snapshot["top_titles"] = [normalize_memory_text(title, limit=120) for title in top_titles if normalize_memory_text(title, limit=120)]
    snapshot["last_refreshed_at"] = _iso_now()
    return dossier


def sync_dashboard_snapshot(dossier: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return dossier

    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    costs = metrics.get("costs") if isinstance(metrics.get("costs"), dict) else {}
    operating = metrics.get("operating_result") if isinstance(metrics.get("operating_result"), dict) else {}
    management_balance = data.get("management_balance") if isinstance(data.get("management_balance"), dict) else {}
    totals = management_balance.get("totals") if isinstance(management_balance.get("totals"), dict) else {}
    operational = data.get("operational_indicators") if isinstance(data.get("operational_indicators"), dict) else {}
    operational_items = operational.get("items") if isinstance(operational.get("items"), list) else []
    sowing = metrics.get("sowing") if isinstance(metrics.get("sowing"), dict) else {}
    harvest = metrics.get("harvest") if isinstance(metrics.get("harvest"), dict) else {}

    snapshot = dossier.setdefault("dashboard_snapshot", {})
    snapshot["operating_result_usd"] = _compact_text(operating.get("result_usd"))
    snapshot["operating_margin_pct"] = _compact_text(operating.get("margin_pct"))
    snapshot["executed_usd"] = _compact_text(costs.get("executed_usd") or totals.get("executed_usd"))
    snapshot["budget_usd"] = _compact_text(costs.get("budget_usd"))
    snapshot["stock_usd"] = _compact_text(totals.get("stock_usd"))
    snapshot["total_hectares"] = _compact_text(
        sowing.get("total_hectares") or harvest.get("total_hectares")
    )
    snapshot["top_operational_items"] = [
        normalize_memory_text(item.get("title"), limit=120)
        for item in operational_items[:4]
        if isinstance(item, dict) and normalize_memory_text(item.get("title"), limit=120)
    ]
    snapshot["last_refreshed_at"] = _iso_now()
    dossier.setdefault("project", {})["last_dashboard_refresh_at"] = snapshot["last_refreshed_at"]
    return dossier


def build_project_operating_context_for_prompt(dossier: dict[str, Any], user_id: str | None = None) -> str:
    consolidate_operational_memory(dossier)
    memory_view = build_operational_memory_view(dossier, user_id)
    project = dossier.get("project", {}) if isinstance(dossier, dict) else {}
    insights_snapshot = dossier.get("insights_snapshot", {}) if isinstance(dossier, dict) else {}
    dashboard_snapshot = dossier.get("dashboard_snapshot", {}) if isinstance(dossier, dict) else {}
    workspace = dossier.get("workspace", {}) if isinstance(dossier, dict) else {}
    insight_chat_context = {}
    if isinstance(dossier, dict):
        if isinstance(dossier.get("insight_chat_context"), dict):
            insight_chat_context = dossier.get("insight_chat_context", {})
        elif isinstance(dossier.get("copilot_context"), dict):
            insight_chat_context = dossier.get("copilot_context", {})

    context: list[str] = []
    context.append("Cómo funciona Ponti:")
    context.extend(f"- {line}" for line in _SOFTWARE_PLAYBOOK)
    context.append("Cómo pensar el dominio agrícola:")
    context.extend(f"- {line}" for line in _AGRICULTURE_PLAYBOOK)

    if project_name := _compact_text(project.get("name")):
        context.append(f"Proyecto actual: {project_name}.")
    if customer_name := _compact_text(project.get("customer_name")):
        context.append(f"Cliente del proyecto: {customer_name}.")
    if campaign_name := _compact_text(project.get("campaign_name")):
        context.append(f"Campaña principal: {campaign_name}.")
    if surface := _compact_text(project.get("surface_hectares")):
        context.append(f"Superficie conocida: {surface} ha.")
    if managers := project.get("managers"):
        context.append(f"Responsables: {', '.join(str(item) for item in managers[:4])}.")
    field_summaries = [
        normalize_memory_text(field.get("name"), limit=120)
        for field in project.get("fields", [])[:4]
        if isinstance(field, dict) and normalize_memory_text(field.get("name"), limit=120)
    ]
    if field_summaries:
        context.append(f"Campos conocidos: {', '.join(field_summaries)}.")

    if insights_snapshot:
        total = int(insights_snapshot.get("new_count_total") or 0)
        high = int(insights_snapshot.get("new_count_high_severity") or 0)
        context.append(f"Insights activos recientes: {total} total, {high} de alta severidad.")
        top_titles = insights_snapshot.get("top_titles", [])[:3]
        if top_titles:
            context.append("Insights destacados:")
            context.extend(f"- {title}" for title in top_titles if title)

    route_hint = _compact_text(workspace.get("last_route_hint"))
    if route_hint:
        context.append(f"Última ruta usada en el chat: {route_hint}.")
    recent_hints = [normalize_memory_text(item, limit=60) for item in workspace.get("recent_route_hints", [])[-3:] if normalize_memory_text(item, limit=60)]
    if recent_hints:
        context.append(f"Rutas recientes del usuario: {', '.join(recent_hints)}.")

    if insight_chat_context:
        insight_chat_bits: list[str] = []
        if insight_id := _compact_text(insight_chat_context.get("insight_id")):
            insight_chat_bits.append(f"insight {insight_id}")
        if scope := _compact_text(insight_chat_context.get("scope")):
            insight_chat_bits.append(f"scope {scope}")
        if notification_id := _compact_text(insight_chat_context.get("notification_id")):
            insight_chat_bits.append(f"notification {notification_id}")
        if routed_agent := _compact_text(insight_chat_context.get("routed_agent")):
            insight_chat_bits.append(f"agente {routed_agent}")
        if insight_chat_bits:
            context.append("Último handoff contextual activo: " + ", ".join(insight_chat_bits) + ".")
        if suggested := _compact_text(insight_chat_context.get("suggested_user_message")):
            context.append(f"Mensaje sugerido reciente para el chat: {suggested}.")

    if dashboard_snapshot:
        executive_bits = [
            ("resultado operativo USD", _compact_text(dashboard_snapshot.get("operating_result_usd"))),
            ("margen operativo %", _compact_text(dashboard_snapshot.get("operating_margin_pct"))),
            ("costos ejecutados USD", _compact_text(dashboard_snapshot.get("executed_usd"))),
            ("presupuesto USD", _compact_text(dashboard_snapshot.get("budget_usd"))),
            ("stock USD", _compact_text(dashboard_snapshot.get("stock_usd"))),
        ]
        executive_bits = [f"{label}: {value}" for label, value in executive_bits if value]
        if executive_bits:
            context.append("Último snapshot ejecutivo:")
            context.extend(f"- {item}" for item in executive_bits)
        top_ops = dashboard_snapshot.get("top_operational_items", [])[:3]
        if top_ops:
            context.append("Indicadores operativos recientes:")
            context.extend(f"- {item}" for item in top_ops if item)

    stable_facts = [item for item in memory_view["stable_business_facts"][-4:] if item]
    if stable_facts:
        context.append("Memoria estable del proyecto:")
        context.extend(f"- {item}" for item in stable_facts)
    open_loops = [item for item in memory_view["open_loops"][-3:] if item]
    if open_loops:
        context.append("Temas abiertos recientes:")
        context.extend(f"- {item}" for item in open_loops)
    decisions = [item for item in memory_view["decisions"][-3:] if item]
    if decisions:
        context.append("Decisiones recientes:")
        context.extend(f"- {item}" for item in decisions)
    if user_id:
        preferences = [item for item in memory_view["active_preferences"][-4:] if item]
        if preferences:
            context.append("Memoria del usuario interno:")
            context.extend(f"- {item}" for item in preferences)
        recent_topics = [item for item in memory_view["recent_topics"][-3:] if item]
        if recent_topics:
            context.append("Temas recientes del usuario:")
            context.extend(f"- {item}" for item in recent_topics)

    return "\n".join(context).strip()
