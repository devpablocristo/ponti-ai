"""Tests para src/insights/ (nueva estructura)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from src.insights.domain import (
    AuditRecord,
    ComputeInsightsResult,
    FeatureValue,
    Insight,
    InsightActionItem,
    InsightHistoryItem,
    InsightSummary,
    StoredProposal,
)
from src.insights.service import ComputeInsights, GetInsights, GetSummary, RecordAction


def _make_insight(
    project_id: str = "p1",
    insight_id: str = "ins-1",
    severity: int = 80,
    status: str = "new",
    n_samples: int = 60,
) -> Insight:
    now = datetime.now(timezone.utc)
    return Insight(
        id=insight_id,
        project_id=project_id,
        entity_type="project",
        entity_id=project_id,
        type="anomaly",
        severity=severity,
        priority=severity,
        title="Alerta de costo",
        summary="Costo fuera de rango.",
        evidence={"feature": "cost_total", "n_samples": n_samples, "window": "all"},
        explanations={"rule": "test"},
        action={"suggestion": "Revisar"},
        model_version="test",
        features_version="test",
        computed_at=now,
        valid_until=now + timedelta(days=7),
        status=status,
    )


class FakeFeatureRepo:
    def fetch_features(self, project_id: str) -> list[FeatureValue]:
        return [FeatureValue(project_id=project_id, entity_type="project", entity_id=project_id, feature_name="cost_total", window="all", value=20.0)]


class FakeModelRunner:
    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        return [_make_insight(project_id=project_id)]


class FakeInsightRepo:
    def __init__(self) -> None:
        self.items: list[Insight] = []

    def upsert_many(self, insights: list[Insight]) -> int:
        self.items.extend(insights)
        return len(insights)

    def get_by_entity(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        return [i for i in self.items if i.project_id == project_id and i.entity_id == entity_id]

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        return next((i for i in self.items if i.project_id == project_id and i.id == insight_id), None)

    def get_summary(self, project_id: str) -> InsightSummary:
        new_items = [i for i in self.items if i.project_id == project_id and i.status == "new"]
        high = [i for i in new_items if i.severity >= 80]
        return InsightSummary(new_count_total=len(new_items), new_count_high_severity=len(high), top_insights=new_items[:3])

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        for idx, item in enumerate(self.items):
            if item.id == insight_id and item.project_id == project_id:
                self.items[idx] = replace(item, status=new_status)
                return

    def get_active_by_dedupe(self, project_id: str, entity_type: str, entity_id: str, dedupe_key: str) -> Insight | None:
        return next(
            (i for i in self.items if i.project_id == project_id and i.entity_type == entity_type and i.entity_id == entity_id and i.dedupe_key == dedupe_key and i.status == "new"),
            None,
        )


class FakeAuditLogger:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def log(self, record: AuditRecord) -> None:
        self.records.append(record)


class FakeProposalStore:
    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        return None

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        return None

    def insert(self, **kwargs) -> str:
        return "prop-1"


class FakePlanner:
    def plan(self, *, insight, historical_context, domain, max_actions_allowed) -> dict:
        return {"classification": {"severity": "high"}, "proposed_plan": []}


class FakeHistory:
    def get_history(self, project_id, entity_type, entity_id, limit=10):
        return []

    def get_recent_actions(self, project_id, limit=10):
        return []


# --- ComputeInsights ---


def test_compute_insights_creates_records() -> None:
    repo = FakeInsightRepo()
    use_case = ComputeInsights(
        FakeFeatureRepo(), FakeModelRunner(), repo, FakeAuditLogger(),
        FakeProposalStore(), FakePlanner(), FakeHistory(),
        domain="agriculture", max_actions_allowed=4, llm_provider="stub", llm_model="stub",
    )
    result = use_case.handle(project_id="p1", user_id="u1")
    assert result.insights_created == 1
    assert result.rules_insights_created == 1
    assert len(result.projected_insights) == 1
    assert result.projected_insights[0].id == "ins-1"


def test_compute_insights_logs_audit() -> None:
    audit = FakeAuditLogger()
    use_case = ComputeInsights(
        FakeFeatureRepo(), FakeModelRunner(), FakeInsightRepo(), audit,
        FakeProposalStore(), FakePlanner(), FakeHistory(),
        domain="agriculture", max_actions_allowed=4, llm_provider="stub", llm_model="stub",
    )
    use_case.handle(project_id="p1", user_id="u1")
    assert len(audit.records) == 1
    assert audit.records[0].question == "insights_compute"
    assert audit.records[0].status == "ok"


# --- GetSummary ---


def test_get_summary_returns_counts() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight(severity=90), _make_insight(insight_id="ins-2", severity=50)]
    use_case = GetSummary(repo)
    summary = use_case.handle("p1")
    assert summary.new_count_total == 2
    assert summary.new_count_high_severity == 1
    assert len(summary.top_insights) == 2


def test_get_summary_empty() -> None:
    use_case = GetSummary(FakeInsightRepo())
    summary = use_case.handle("p1")
    assert summary.new_count_total == 0
    assert summary.new_count_high_severity == 0


# --- GetInsights ---


def test_get_insights_by_entity() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight(), _make_insight(project_id="p2", insight_id="ins-2")]
    use_case = GetInsights(repo)
    result = use_case.handle("p1", "project", "p1")
    assert len(result) == 1
    assert result[0].id == "ins-1"


# --- RecordAction ---


def test_record_action_changes_status() -> None:
    repo = FakeInsightRepo()
    repo.items = [_make_insight()]
    audit = FakeAuditLogger()
    use_case = RecordAction(repo, audit)
    result = use_case.handle("ins-1", "p1", "u1", "acknowledge", "acknowledged")
    assert result.request_id
    assert repo.items[0].status == "acknowledged"
    assert len(audit.records) == 1
