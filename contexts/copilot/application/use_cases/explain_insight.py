from contextlib import nullcontext
from typing import Any

from contexts.copilot.application.ports.copilot_explainer import CopilotExplainMode, CopilotExplainerPort
from contexts.insights.application.ports.insight_repository import InsightRepositoryPort
from contexts.insights.application.ports.proposal_store import ProposalStorePort


class InsightNotFoundError(Exception):
    pass


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
            raise InsightNotFoundError("insight_not_found")

        proposal_row = self.proposal_store.get_latest_ok(insight_id)
        proposal = proposal_row.proposal if proposal_row else None

        request_scope = self._explainer_request_scope()
        with request_scope:
            explanation = self.explainer.explain(insight=insight, proposal=proposal, mode=mode)
        return {
            "insight_id": insight.id,
            "mode": mode,
            "explanation": explanation,
            "proposal": proposal,
        }

    def _explainer_request_scope(self):
        request_scope = getattr(self.explainer, "request_scope", None)
        if callable(request_scope):
            return request_scope()
        return nullcontext()
