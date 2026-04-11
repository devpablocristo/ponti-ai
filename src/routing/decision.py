"""Output del pipeline de routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HandlerKind = Literal["static_reply", "insight_lane", "direct_agent", "orchestrator"]


@dataclass(frozen=True)
class RoutingDecision:
    handler_kind: HandlerKind
    target: str
    reason: str
    extras: dict[str, Any] = field(default_factory=dict)
