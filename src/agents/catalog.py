"""Catálogo de agentes y funciones de normalización (estilo Pymes)."""

from __future__ import annotations

from typing import Final

from src.runtime_contracts import (
    ROUTING_SOURCE_COPILOT_AGENT,
    ROUTING_SOURCE_INSIGHT_CHAT_AGENT,
    ROUTING_SOURCE_ORCHESTRATOR,
    ROUTING_SOURCE_READ_FALLBACK,
    ROUTING_SOURCE_UI_HINT,
)

PRODUCT_AGENT_NAME: Final[str] = "general"
INSIGHT_CHAT_AGENT_NAME: Final[str] = "insight_chat"

DASHBOARD_AGENT_NAME: Final[str] = "dashboard"
LABORS_AGENT_NAME: Final[str] = "labors"
SUPPLIES_AGENT_NAME: Final[str] = "supplies"
CAMPAIGNS_AGENT_NAME: Final[str] = "campaigns"
LOTS_AGENT_NAME: Final[str] = "lots"
STOCK_AGENT_NAME: Final[str] = "stock"
REPORTS_AGENT_NAME: Final[str] = "reports"

DOMAIN_AGENT_NAMES: Final[tuple[str, ...]] = (
    DASHBOARD_AGENT_NAME,
    LABORS_AGENT_NAME,
    SUPPLIES_AGENT_NAME,
    CAMPAIGNS_AGENT_NAME,
    LOTS_AGENT_NAME,
    STOCK_AGENT_NAME,
    REPORTS_AGENT_NAME,
)

ALL_ROUTED_AGENT_NAMES: Final[tuple[str, ...]] = (
    PRODUCT_AGENT_NAME,
    INSIGHT_CHAT_AGENT_NAME,
    *DOMAIN_AGENT_NAMES,
)


def is_known_routed_agent(name: str | None) -> bool:
    return bool(name and name in ALL_ROUTED_AGENT_NAMES)


def normalize_routed_agent(name: str | None) -> str:
    if is_known_routed_agent(name):
        return str(name)
    return PRODUCT_AGENT_NAME


def is_known_routing_source(name: str | None) -> bool:
    return bool(
        name
        and name
        in {
            ROUTING_SOURCE_COPILOT_AGENT,
            ROUTING_SOURCE_INSIGHT_CHAT_AGENT,
            ROUTING_SOURCE_ORCHESTRATOR,
            ROUTING_SOURCE_READ_FALLBACK,
            ROUTING_SOURCE_UI_HINT,
        }
    )


def normalize_routing_source(name: str | None) -> str:
    if name == ROUTING_SOURCE_COPILOT_AGENT:
        return ROUTING_SOURCE_INSIGHT_CHAT_AGENT
    if is_known_routing_source(name):
        return str(name)
    return ROUTING_SOURCE_ORCHESTRATOR
