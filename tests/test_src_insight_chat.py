"""Tests para src/insight_chat."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.insight_chat.service import ExplainInsight, InsightNotFoundError
from src.insights.domain import Insight, InsightSummary, StoredProposal


def _make_insight(project_id: str = "p1", insight_id: str = "ins-1") -> Insight:
    now = datetime.now(timezone.utc)
    return Insight(
        id=insight_id, project_id=project_id, entity_type="project", entity_id=project_id,
        type="anomaly", severity=80, priority=80, title="Alerta de costo", summary="Costo fuera de rango.",
        evidence={"feature": "cost_total"}, explanations={"rule": "test"}, action={"suggestion": "Revisar"},
        model_version="test", features_version="test", computed_at=now, valid_until=now + timedelta(days=7), status="new",
    )


class FakeInsightRepo:
    def __init__(self) -> None:
        self.items: list[Insight] = []

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        return next((i for i in self.items if i.project_id == project_id and i.id == insight_id), None)


class FakeProposalStore:
    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        return None


class FakeExplainer:
    def explain(self, *, insight, proposal, mode) -> dict[str, str]:
        return {
            "human_readable": f"Explicación {mode}: {insight.title}",
            "audit_focused": "Evidencia de auditoría",
            "what_to_watch_next": "Monitorear recurrencia",
        }

    def request_scope(self):
        from contextlib import nullcontext
        return nullcontext()


def test_explain_insight_returns_explanation() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight()]
    use_case = ExplainInsight(
        insight_repo=repo,
        proposal_store=FakeProposalStore(),
        explainer=FakeExplainer(),
    )
    result = use_case.handle(project_id="p1", insight_id="ins-1", mode="explain")
    assert result["insight_id"] == "ins-1"
    assert result["mode"] == "explain"
    assert "Explicación explain" in result["explanation"]["human_readable"]


def test_explain_insight_why_mode() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight()]
    use_case = ExplainInsight(
        insight_repo=repo,
        proposal_store=FakeProposalStore(),
        explainer=FakeExplainer(),
    )
    result = use_case.handle(project_id="p1", insight_id="ins-1", mode="why")
    assert result["mode"] == "why"
    assert "why" in result["explanation"]["human_readable"]


def test_explain_insight_next_steps_mode() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight()]
    use_case = ExplainInsight(
        insight_repo=repo,
        proposal_store=FakeProposalStore(),
        explainer=FakeExplainer(),
    )
    result = use_case.handle(project_id="p1", insight_id="ins-1", mode="next-steps")
    assert result["mode"] == "next-steps"


def test_explain_insight_not_found_raises() -> None:
    use_case = ExplainInsight(
        insight_repo=FakeInsightRepo(),
        proposal_store=FakeProposalStore(),
        explainer=FakeExplainer(),
    )
    with pytest.raises(InsightNotFoundError):
        use_case.handle(project_id="p1", insight_id="nonexistent", mode="explain")
