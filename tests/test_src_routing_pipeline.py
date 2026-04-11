"""Tests parametrizados del pipeline de routing (estilo Pymes)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.routing import TurnContext
from src.routing.resolve import resolve_routing_decision


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "context", "expected_kind", "expected_target", "expected_reason"),
    [
        (
            "menu_request",
            TurnContext(message="menú", route_hint="labors", is_menu_request=True),
            "static_reply",
            "route_menu",
            "menu_request",
        ),
        (
            "ambiguous_without_hint",
            TurnContext(message="cuánto hay", is_ambiguous_query=True),
            "static_reply",
            "route_clarification",
            "ambiguous_query",
        ),
        (
            "structured_handoff",
            TurnContext(
                message="explicame este insight",
                handoff=SimpleNamespace(
                    source="in_app_notification",
                    notification_id="notif-1",
                    insight_id="ins-1",
                    insight_scope="project:p1",
                    period="month",
                ),
                handoff_is_structured_insight=True,
                handoff_is_valid=True,
            ),
            "insight_lane",
            "project:p1",
            "structured_handoff",
        ),
        (
            "explicit_domain_hint_labors",
            TurnContext(message="mostrame labores", route_hint="labors", route_hint_source="explicit"),
            "direct_agent",
            "labors",
            "explicit_route_hint",
        ),
        (
            "explicit_domain_hint_stock",
            TurnContext(message="stock de urea", route_hint="stock", route_hint_source="explicit"),
            "direct_agent",
            "stock",
            "explicit_route_hint",
        ),
        (
            "legacy_insight_chat_with_match",
            TurnContext(
                message="explicame este insight",
                route_hint="insight_chat",
                route_hint_source="explicit",
                legacy_insight_request=SimpleNamespace(scope="anomaly", insight_id="ins-1"),
                legacy_insight_match=True,
            ),
            "insight_lane",
            "anomaly",
            "legacy_insight_hint",
        ),
        (
            "insight_chat_without_match",
            TurnContext(
                message="hola",
                route_hint="insight_chat",
                route_hint_source="explicit",
                legacy_insight_request=None,
                legacy_insight_match=False,
            ),
            "orchestrator",
            "general",
            "no_deterministic_match",
        ),
        (
            "no_hint_no_handoff",
            TurnContext(message="hola"),
            "orchestrator",
            "general",
            "no_deterministic_match",
        ),
    ],
)
async def test_resolve_routing_decision_pipeline_table(
    name: str,
    context: TurnContext,
    expected_kind: str,
    expected_target: str,
    expected_reason: str,
) -> None:
    _ = name
    decision = await resolve_routing_decision(context)
    assert decision.handler_kind == expected_kind
    assert decision.target == expected_target
    assert decision.reason == expected_reason


@pytest.mark.anyio
async def test_handoff_takes_precedence_over_explicit_hint() -> None:
    context = TurnContext(
        message="hola",
        route_hint="labors",
        route_hint_source="explicit",
        handoff=SimpleNamespace(
            source="in_app_notification",
            notification_id="notif-1",
            insight_id="ins-2",
            insight_scope="cost_anomaly",
            period="week",
        ),
        handoff_is_structured_insight=True,
        handoff_is_valid=True,
    )
    decision = await resolve_routing_decision(context)
    assert decision.handler_kind == "insight_lane"
    assert decision.target == "cost_anomaly"
    assert decision.reason == "structured_handoff"


@pytest.mark.anyio
async def test_invalid_handoff_falls_to_explicit_hint() -> None:
    context = TurnContext(
        message="mostrame labores",
        route_hint="labors",
        route_hint_source="explicit",
        handoff=SimpleNamespace(
            source="in_app_notification",
            notification_id="notif-404",
            insight_id="ins-1",
            insight_scope="cost_anomaly",
        ),
        handoff_is_structured_insight=True,
        handoff_is_valid=False,
    )
    decision = await resolve_routing_decision(context)
    assert decision.handler_kind == "direct_agent"
    assert decision.target == "labors"
    assert decision.reason == "explicit_route_hint"


# --- Detección de menú y ambigüedad ---


def test_menu_detection() -> None:
    from src.agents.service import _looks_like_menu_request
    assert _looks_like_menu_request("menú") is True
    assert _looks_like_menu_request("menu") is True
    assert _looks_like_menu_request("opciones") is True
    assert _looks_like_menu_request("hola") is False


def test_ambiguous_detection() -> None:
    from src.agents.service import _looks_like_ambiguous_query
    assert _looks_like_ambiguous_query("cuánto hay") is True
    assert _looks_like_ambiguous_query("resumen") is True
    assert _looks_like_ambiguous_query("mostrame las labores") is False
