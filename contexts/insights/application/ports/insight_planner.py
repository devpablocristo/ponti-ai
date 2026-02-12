from typing import Any, Protocol

from contexts.insights.domain.entities import Insight


class InsightPlannerPort(Protocol):
    def plan(
        self,
        *,
        insight: Insight,
        historical_context: dict[str, Any],
        domain: str,
        max_actions_allowed: int,
    ) -> dict[str, Any]:
        ...
