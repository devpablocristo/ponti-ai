"""Use case: explicar un insight vía insight_chat."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any


class InsightNotFoundError(Exception):
    def __init__(self, insight_id: str) -> None:
        super().__init__(f"Insight {insight_id} no encontrado")
        self.insight_id = insight_id


class ExplainInsight:
    def __init__(self, *, insight_repo, proposal_store, explainer) -> None:
        self.insight_repo = insight_repo
        self.proposal_store = proposal_store
        self.explainer = explainer

    def handle(self, *, project_id: str, insight_id: str, mode: str) -> dict[str, Any]:
        insight = self.insight_repo.get_by_id(project_id, insight_id)
        if insight is None:
            raise InsightNotFoundError(insight_id)

        proposal_record = self.proposal_store.get_latest_ok(insight_id)
        proposal = proposal_record.proposal if proposal_record else None

        request_scope = self._explainer_request_scope()
        with request_scope:
            explanation = self.explainer.explain(insight=insight, proposal=proposal, mode=mode)

        return {
            "insight_id": insight_id,
            "mode": mode,
            "explanation": explanation,
            "proposal": proposal,
        }

    def _explainer_request_scope(self):
        request_scope = getattr(self.explainer, "request_scope", None)
        if callable(request_scope):
            return request_scope()
        return nullcontext()

