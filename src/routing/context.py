"""Input inmutable para el pipeline de routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnContext:
    """Minimal, side-effect-free input for the routing pipeline."""

    message: str
    route_hint: str | None = None
    route_hint_source: str | None = None
    handoff: Any | None = None
    legacy_insight_request: Any | None = None
    is_menu_request: bool = False
    is_ambiguous_query: bool = False
    handoff_is_structured_insight: bool = False
    handoff_is_valid: bool = False
    handoff_validation_reason: str = ""
    legacy_insight_match: bool = False
