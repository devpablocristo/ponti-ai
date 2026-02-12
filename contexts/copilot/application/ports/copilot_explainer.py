from typing import Any, Literal, Protocol

from contexts.insights.domain.entities import Insight


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

