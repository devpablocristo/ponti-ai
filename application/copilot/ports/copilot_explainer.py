from typing import Any, Literal, Protocol

from domain.insights.entities import Insight


CopilotExplainMode = Literal["explain", "why", "next_steps"]


class CopilotExplainerPort(Protocol):
    def explain(
        self,
        *,
        insight: Insight,
        proposal: dict[str, Any] | None,
        mode: CopilotExplainMode,
    ) -> dict[str, str]:
        ...

