"""Pipeline determinista de routing (5 etapas)."""

from __future__ import annotations

from src.agents.catalog import INSIGHT_CHAT_AGENT_NAME, PRODUCT_AGENT_NAME
from src.routing.context import TurnContext
from src.routing.decision import RoutingDecision


async def resolve_routing_decision(context: TurnContext) -> RoutingDecision:
    """Resolve deterministic routing before any LLM orchestration."""

    # Routing stages:
    # 1) hard UI/static rules (menu, clarification)
    # 2) structured insight handoff
    # 3) explicit domain hint
    # 4) legacy insight_chat hint
    # 5) orchestrator fallback
    normalized_route_hint = str(context.route_hint or "").strip().lower() or None

    # 1) Menu request
    if normalized_route_hint != INSIGHT_CHAT_AGENT_NAME and context.is_menu_request:
        return RoutingDecision(
            handler_kind="static_reply",
            target="route_menu",
            reason="menu_request",
        )

    # 2) Ambiguous query → clarification
    if normalized_route_hint is None and context.is_ambiguous_query:
        return RoutingDecision(
            handler_kind="static_reply",
            target="route_clarification",
            reason="ambiguous_query",
        )

    # 3) Structured insight handoff
    if context.handoff_is_structured_insight and context.handoff_is_valid and context.handoff is not None:
        return RoutingDecision(
            handler_kind="insight_lane",
            target=str(getattr(context.handoff, "insight_scope", "") or "insight"),
            reason="structured_handoff",
            extras={
                "source": getattr(context.handoff, "source", ""),
                "notification_id": getattr(context.handoff, "notification_id", None),
                "insight_id": getattr(context.handoff, "insight_id", None),
                "period": getattr(context.handoff, "period", None),
            },
        )

    # 4) Explicit domain hint (not insight_chat, not general)
    if normalized_route_hint not in {None, INSIGHT_CHAT_AGENT_NAME, PRODUCT_AGENT_NAME}:
        return RoutingDecision(
            handler_kind="direct_agent",
            target=normalized_route_hint,
            reason="explicit_route_hint",
        )

    # 5) Legacy insight_chat match (route_hint=insight_chat + keyword match)
    if normalized_route_hint == INSIGHT_CHAT_AGENT_NAME and context.legacy_insight_match:
        legacy_request = context.legacy_insight_request
        return RoutingDecision(
            handler_kind="insight_lane",
            target=str(getattr(legacy_request, "scope", "insight") if legacy_request else "insight"),
            reason="legacy_insight_hint",
            extras={
                "source": "insight_chat_legacy_match",
                "notification_id": None,
                "insight_id": getattr(legacy_request, "insight_id", None) if legacy_request else None,
            },
        )

    # Fallback → orchestrator
    return RoutingDecision(
        handler_kind="orchestrator",
        target="general",
        reason="no_deterministic_match",
    )
