from typing import Any

from application.copilot.ports.copilot_explainer import CopilotExplainMode, CopilotExplainerPort
from application.insights.ports.insight_repository import InsightRepositoryPort
from application.insights.ports.proposal_store import ProposalStorePort


class ExplainInsight:
    def __init__(
        self,
        *,
        insight_repo: InsightRepositoryPort,
        proposal_store: ProposalStorePort,
        explainer: CopilotExplainerPort,
    ) -> None:
        self.insight_repo = insight_repo
        self.proposal_store = proposal_store
        self.explainer = explainer

    def handle(self, *, project_id: str, insight_id: str, mode: CopilotExplainMode) -> dict[str, Any]:
        insight = self.insight_repo.get_by_id(project_id, insight_id)
        if insight is None:
            raise KeyError("insight_not_found")

        proposal_row = self.proposal_store.get_latest_ok(insight_id)
        proposal = proposal_row.proposal if proposal_row else None

        explanation = self.explainer.explain(insight=insight, proposal=proposal, mode=mode)
        return {
            "insight_id": insight.id,
            "mode": mode,
            "explanation": explanation,
            "proposal": proposal,
        }

