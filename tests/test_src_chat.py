"""Tests para src/agents/service.py y src/agents/catalog.py (nueva estructura)."""

from __future__ import annotations

from src.agents.catalog import (
    ALL_ROUTED_AGENT_NAMES,
    DASHBOARD_AGENT_NAME,
    INSIGHT_CHAT_AGENT_NAME,
    LABORS_AGENT_NAME,
    PRODUCT_AGENT_NAME,
    is_known_routed_agent,
    normalize_routed_agent,
    normalize_routing_source,
)
from src.agents.service import (
    _infer_read_route,
    _looks_executive_request,
    _looks_like_contextual_follow_up,
    _looks_like_insight_chat_request,
    _resolve_language,
    _resolve_route,
)
from src.runtime_contracts import ROUTING_SOURCE_INSIGHT_CHAT_AGENT, ROUTING_SOURCE_ORCHESTRATOR, ROUTING_SOURCE_READ_FALLBACK, ROUTING_SOURCE_UI_HINT


# --- catalog ---


def test_all_routed_agent_names_includes_insight_chat() -> None:
    assert INSIGHT_CHAT_AGENT_NAME in ALL_ROUTED_AGENT_NAMES
    assert "copilot" not in ALL_ROUTED_AGENT_NAMES


def test_normalize_routed_agent_known() -> None:
    assert normalize_routed_agent("dashboard") == DASHBOARD_AGENT_NAME
    assert normalize_routed_agent("insight_chat") == INSIGHT_CHAT_AGENT_NAME


def test_normalize_routed_agent_unknown_falls_to_general() -> None:
    assert normalize_routed_agent("unknown") == PRODUCT_AGENT_NAME
    assert normalize_routed_agent(None) == PRODUCT_AGENT_NAME
    assert normalize_routed_agent("copilot") == PRODUCT_AGENT_NAME


def test_is_known_routed_agent() -> None:
    assert is_known_routed_agent("dashboard") is True
    assert is_known_routed_agent("copilot") is False
    assert is_known_routed_agent(None) is False


def test_normalize_routing_source() -> None:
    assert normalize_routing_source("orchestrator") == ROUTING_SOURCE_ORCHESTRATOR
    assert normalize_routing_source("copilot_agent") == ROUTING_SOURCE_INSIGHT_CHAT_AGENT
    assert normalize_routing_source("unknown") == ROUTING_SOURCE_ORCHESTRATOR


# --- service routing helpers ---


def test_looks_executive_request() -> None:
    assert _looks_executive_request("como viene el proyecto") is True
    assert _looks_executive_request("hola que tal") is False


def test_looks_like_contextual_follow_up() -> None:
    assert _looks_like_contextual_follow_up("explicame eso") is True
    assert _looks_like_contextual_follow_up("quiero ver labores") is False


def test_looks_like_insight_chat_request_with_context() -> None:
    assert _looks_like_insight_chat_request("hola", {"notification_id": "n1"}) is True
    assert _looks_like_insight_chat_request("hola", {"insight_id": "i1"}) is True
    assert _looks_like_insight_chat_request("hola", None) is False
    assert _looks_like_insight_chat_request("hola", {}) is False


def test_looks_like_insight_chat_request_by_message() -> None:
    assert _looks_like_insight_chat_request("explicame este insight", None) is True
    assert _looks_like_insight_chat_request("dame la lista", None) is False


def test_infer_read_route_dashboard() -> None:
    assert _infer_read_route("resumen ejecutivo del proyecto") == DASHBOARD_AGENT_NAME


def test_infer_read_route_labors() -> None:
    assert _infer_read_route("mostrame las labores") == LABORS_AGENT_NAME


def test_infer_read_route_none() -> None:
    assert _infer_read_route("hola como estas") is None


def test_resolve_route_no_hint_no_context() -> None:
    agent, source = _resolve_route(None, "hola")
    assert agent == PRODUCT_AGENT_NAME
    assert source == ROUTING_SOURCE_ORCHESTRATOR


def test_resolve_route_explicit_hint() -> None:
    agent, source = _resolve_route("labors", "mostrame todo")
    assert agent == LABORS_AGENT_NAME
    assert source == ROUTING_SOURCE_UI_HINT


def test_resolve_route_insight_chat_with_context() -> None:
    agent, source = _resolve_route("insight_chat", "explicame este insight", chat_context={"insight_id": "i1"})
    assert agent == INSIGHT_CHAT_AGENT_NAME
    assert source == ROUTING_SOURCE_INSIGHT_CHAT_AGENT


def test_resolve_route_infers_dashboard_for_executive() -> None:
    agent, source = _resolve_route(None, "como viene el proyecto")
    assert agent == DASHBOARD_AGENT_NAME
    assert source == ROUTING_SOURCE_READ_FALLBACK


def test_resolve_language_defaults_to_es() -> None:
    assert _resolve_language(None, None) == "es"
    assert _resolve_language("es", None) == "es"


def test_resolve_language_en() -> None:
    assert _resolve_language("en", None) == "en"
    assert _resolve_language(None, "en-US,en;q=0.9") == "en"
