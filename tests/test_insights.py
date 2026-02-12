from datetime import datetime, timedelta, timezone

import pytest

from contexts.insights.application.ports.feature_repository import FeatureRepositoryPort, FeatureValue
from contexts.insights.application.ports.insight_history import InsightActionItem, InsightHistoryItem, InsightHistoryPort
from contexts.insights.application.ports.insight_repository import InsightRepositoryPort, InsightSummary
from contexts.insights.application.ports.insight_planner import InsightPlannerPort
from contexts.insights.application.ports.ml_detector import MLDetectorPort
from contexts.insights.application.ports.model_runner import ModelRunnerPort
from contexts.insights.application.ports.baseline_repository import BaselineRecord, BaselineRepositoryPort
from contexts.insights.application.ports.proposal_store import ProposalStorePort, StoredProposal
from contexts.insights.application.use_cases.compute_insights import ComputeInsights
from contexts.insights.application.use_cases.get_summary import GetSummary
from contexts.insights.application.use_cases.record_action import RecordAction
from contexts.copilot.application.ports.audit_logger import AuditLoggerPort, AuditRecord
from contexts.insights.domain.entities import Insight


class FakeFeatureRepo(FeatureRepositoryPort):
    def fetch_features(self, project_id: str) -> list[FeatureValue]:
        return [
            FeatureValue(
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                feature_name="cost_total",
                window="all",
                value=20.0,
            )
        ]


class FakeModelRunner(ModelRunnerPort):
    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        now = datetime.now(timezone.utc)
        return [
            Insight(
                id="ins-1",
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                type="anomaly",
                severity=80,
                priority=80,
                title="Alerta de costo",
                summary="Costo fuera de rango.",
                evidence={"feature": "cost_total", "n_samples": 60, "window": "all", "p90": 30.0, "value": 40.0},
                explanations={"rule": "test"},
                action={"suggestion": "Revisar"},
                model_version="test",
                features_version="test",
                computed_at=now,
                valid_until=now + timedelta(days=7),
                status="new",
            )
        ]


class FakeInsightRepo(InsightRepositoryPort):
    def __init__(self) -> None:
        self.items: list[Insight] = []

    def upsert_many(self, insights: list[Insight]) -> int:
        self.items.extend(insights)
        return len(insights)

    def get_by_entity(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        return [i for i in self.items if i.project_id == project_id and i.entity_id == entity_id]

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        for i in self.items:
            if i.project_id == project_id and i.id == insight_id:
                return i
        return None

    def get_summary(self, project_id: str) -> InsightSummary:
        new_items = [i for i in self.items if i.project_id == project_id and i.status == "new"]
        high = [i for i in new_items if i.severity >= 80]
        return InsightSummary(new_count_total=len(new_items), new_count_high_severity=len(high), top_insights=new_items[:3])

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        for idx, i in enumerate(self.items):
            if i.id == insight_id and i.project_id == project_id:
                self.items[idx] = Insight(
                    id=i.id,
                    project_id=i.project_id,
                    entity_type=i.entity_type,
                    entity_id=i.entity_id,
                    type=i.type,
                    severity=i.severity,
                    priority=i.priority,
                    title=i.title,
                    summary=i.summary,
                    evidence=i.evidence,
                    explanations=i.explanations,
                    action=i.action,
                    model_version=i.model_version,
                    features_version=i.features_version,
                    computed_at=i.computed_at,
                    valid_until=i.valid_until,
                    status=new_status,
                    impact_min=i.impact_min,
                    impact_max=i.impact_max,
                    impact_unit=i.impact_unit,
                    confidence=i.confidence,
                    dedupe_key=i.dedupe_key,
                    cooldown_until=i.cooldown_until,
                    computed_by=i.computed_by,
                    job_run_id=i.job_run_id,
                    rules_version=i.rules_version,
                )
                return

    def mark_recomputed(self, project_id: str) -> None:
        return None

    def get_active_by_dedupe(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        dedupe_key: str,
    ) -> Insight | None:
        for i in self.items:
            if (
                i.project_id == project_id
                and i.entity_type == entity_type
                and i.entity_id == entity_id
                and i.dedupe_key == dedupe_key
                and i.status == "new"
            ):
                return i
        return None

    def count_active(self, project_id: str) -> int:
        return len([i for i in self.items if i.project_id == project_id and i.status == "new"])

    def list_active(self, project_id: str, limit: int) -> list[Insight]:
        items = [i for i in self.items if i.project_id == project_id and i.status == "new"]
        return items[:limit]


class FakeAuditLogger(AuditLoggerPort):
    def log(self, record: AuditRecord) -> None:
        return None


class FakeProposalStore(ProposalStorePort):
    def __init__(self) -> None:
        self.items: list[StoredProposal] = []

    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        ok = [p for p in self.items if p.insight_id == insight_id and p.status == "ok"]
        return ok[-1] if ok else None

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        all_items = [p for p in self.items if p.insight_id == insight_id]
        return all_items[-1] if all_items else None

    def insert(
        self,
        *,
        insight_id: str,
        project_id: str,
        proposal: dict,
        prompt_version: str,
        tools_catalog_version: str,
        llm_provider: str,
        llm_model: str,
        status: str,
        error_message: str | None,
    ) -> str:
        pid = f"prop-{len(self.items)+1}"
        self.items.append(
            StoredProposal(
                id=pid,
                insight_id=insight_id,
                project_id=project_id,
                proposal=proposal,
                prompt_version=prompt_version,
                tools_catalog_version=tools_catalog_version,
                llm_provider=llm_provider,
                llm_model=llm_model,
                status=status,  # type: ignore[arg-type]
                error_message=error_message,
                created_at=datetime.now(timezone.utc),
            )
        )
        return pid


class FakePlanner(InsightPlannerPort):
    def plan(
        self,
        *,
        insight: Insight,
        historical_context: dict,
        domain: str,
        max_actions_allowed: int,
    ) -> dict:
        _ = historical_context
        _ = domain
        _ = max_actions_allowed
        return {
            "classification": {"severity": "high", "actionability": "act", "confidence": 0.85},
            "decision_summary": {"recommended_outcome": "propose_actions", "primary_reason": "test"},
            "proposed_plan": [
                {
                    "step": 1,
                    "action": f"Review {insight.id}",
                    "tool": "request_cost_breakdown",
                    "tool_args": {"feature": "cost_total", "time_window": "all", "project_id": insight.project_id, "insight_id": insight.id},
                    "rationale": "test",
                    "reversible": True,
                }
            ],
            "risks_and_uncertainties": [],
            "explanation": {"human_readable": "x", "audit_focused": "y", "what_to_watch_next": "z"},
        }


class FakeHistory(InsightHistoryPort):
    def get_history(self, project_id: str, entity_type: str, entity_id: str, limit: int) -> list[InsightHistoryItem]:
        _ = project_id
        _ = entity_type
        _ = entity_id
        _ = limit
        return []

    def get_recent_actions(self, project_id: str, limit: int) -> list[InsightActionItem]:
        _ = project_id
        _ = limit
        return []


class FakeMLDetector(MLDetectorPort):
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def detect_anomalies(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        _ = features
        if self.should_fail:
            raise RuntimeError("ml_unavailable")
        now = datetime.now(timezone.utc)
        return [
            Insight(
                id="ins-ml-1",
                project_id=project_id,
                entity_type="project",
                entity_id=project_id,
                type="anomaly",
                severity=85,
                priority=85,
                title="Alerta ML",
                summary="Patron anomalo detectado por ML",
                evidence={"feature": "cost_total", "n_samples": 80, "window": "all", "value": 40.0},
                explanations={"rule": "ml_test"},
                action={"suggestion": "Revisar"},
                model_version="ml-v1",
                features_version="features-v1",
                computed_at=now,
                valid_until=now + timedelta(days=7),
                status="new",
                dedupe_key="ml:anomaly",
                cooldown_until=now + timedelta(days=7),
            )
        ]

def test_compute_insights_creates_records() -> None:
    use_case = ComputeInsights(
        FakeFeatureRepo(),
        FakeModelRunner(),
        FakeInsightRepo(),
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
    )
    result = use_case.handle(project_id="p1", user_id="u1")
    assert result.insights_created == 1


def test_compute_insights_includes_ml_records() -> None:
    repo = FakeInsightRepo()
    use_case = ComputeInsights(
        FakeFeatureRepo(),
        FakeModelRunner(),
        repo,
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
        ml_detector=FakeMLDetector(),
    )
    result = use_case.handle(project_id="p1", user_id="u1")
    assert result.insights_created == 2
    assert result.rules_insights_created == 1
    assert result.ml_insights_created == 1
    assert any(item.id == "ins-ml-1" for item in repo.items)


def test_compute_insights_continues_when_ml_fails() -> None:
    use_case = ComputeInsights(
        FakeFeatureRepo(),
        FakeModelRunner(),
        FakeInsightRepo(),
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
        ml_detector=FakeMLDetector(should_fail=True),
    )
    result = use_case.handle(project_id="p1", user_id="u1")
    assert result.insights_created == 1
    assert result.rules_insights_created == 1
    assert result.ml_insights_created == 0


def test_compute_insights_creates_proposal_when_gating_passes() -> None:
    proposal_store = FakeProposalStore()
    use_case = ComputeInsights(
        FakeFeatureRepo(),
        FakeModelRunner(),
        FakeInsightRepo(),
        FakeAuditLogger(),
        proposal_store,
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
    )
    use_case.handle(project_id="p1", user_id="u1")
    assert proposal_store.get_latest_ok("ins-1") is not None


def test_summary_counts() -> None:
    repo = FakeInsightRepo()
    model = FakeModelRunner()
    features = FakeFeatureRepo()
    ComputeInsights(
        features,
        model,
        repo,
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
    ).handle("p1", "u1")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 1
    assert summary.new_count_high_severity == 1


def test_action_updates_status() -> None:
    repo = FakeInsightRepo()
    model = FakeModelRunner()
    features = FakeFeatureRepo()
    ComputeInsights(
        features,
        model,
        repo,
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
    ).handle("p1", "u1")
    RecordAction(repo, FakeAuditLogger()).handle("ins-1", "p1", "u1", "ignored", "ignored")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 0


def test_action_missing_insight_raises_key_error() -> None:
    repo = FakeInsightRepo()
    with pytest.raises(KeyError):
        RecordAction(repo, FakeAuditLogger()).handle("missing-id", "p1", "u1", "ack", "acknowledged")


def test_compute_insights_respects_cooldown() -> None:
    repo = FakeInsightRepo()
    now = datetime.now(timezone.utc)
    existing = Insight(
        id="ins-cooldown",
        project_id="p1",
        entity_type="project",
        entity_id="p1",
        type="anomaly",
        severity=80,
        priority=80,
        title="Cooldown activo",
        summary="No debe duplicar",
        evidence={},
        explanations={},
        action={},
        model_version="test",
        features_version="test",
        computed_at=now,
        valid_until=now + timedelta(days=7),
        status="new",
        dedupe_key="cost_total:all:anomaly",
        cooldown_until=now + timedelta(days=3),
    )
    repo.items.append(existing)

    class CooldownModel(ModelRunnerPort):
        def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
            return [
                Insight(
                    id="ins-dup",
                    project_id=project_id,
                    entity_type="project",
                    entity_id=project_id,
                    type="anomaly",
                    severity=80,
                    priority=80,
                    title="Duplicado",
                    summary="Debe skippear",
                    evidence={},
                    explanations={},
                    action={},
                    model_version="test",
                    features_version="test",
                    computed_at=now,
                    valid_until=now + timedelta(days=7),
                    status="new",
                    dedupe_key="cost_total:all:anomaly",
                    cooldown_until=now + timedelta(days=3),
                )
            ]

    result = ComputeInsights(
        FakeFeatureRepo(),
        CooldownModel(),
        repo,
        FakeAuditLogger(),
        FakeProposalStore(),
        FakePlanner(),
        FakeHistory(),
        domain="agriculture",
        max_actions_allowed=4,
        llm_provider="stub",
        llm_model="stub",
    ).handle("p1", "u1")
    assert result.insights_created == 0


def test_anomaly_runner_sets_impact_and_confidence() -> None:
    class FakeBaselineRepo(BaselineRepositoryPort):
        def upsert_many(self, records: list[BaselineRecord]) -> int:
            return len(records)

        def get_baseline(
            self,
            scope_type: str,
            scope_id: str | None,
            cohort_key: str,
            feature_name: str,
            window: str,
        ) -> BaselineRecord | None:
            if feature_name != "cost_total":
                return None
            return BaselineRecord(
                scope_type="global",
                scope_id=None,
                cohort_key=cohort_key,
                feature_name=feature_name,
                window=window,
                p50=10.0,
                p75=20.0,
                p90=30.0,
                n_samples=60,
                computed_at=datetime.now(timezone.utc),
            )

    from adapters.outbound.models.anomaly_runner import AnomalyRunner

    runner = AnomalyRunner(
        baseline_repo=FakeBaselineRepo(),
        ratio_high=0.5,
        ratio_medium=0.2,
        spike_ratio=1.5,
        size_small_max=200,
        size_medium_max=1000,
        cooldown_days=7,
        impact_k=1.0,
        impact_cap=2.0,
    )

    features = [
        FeatureValue(
            project_id="p1",
            entity_type="project",
            entity_id="p1",
            feature_name="total_hectares",
            window="all",
            value=150,
        ),
        FeatureValue(
            project_id="p1",
            entity_type="project",
            entity_id="p1",
            feature_name="cost_total",
            window="all",
            value=40.0,
        ),
    ]
    insights = runner.compute("p1", features)
    assert len(insights) == 1
    item = insights[0]
    assert item.impact_min is not None
    assert item.impact_max is not None
    assert item.confidence == "high"
