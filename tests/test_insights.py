from datetime import datetime, timedelta, timezone

import pytest

from contexts.copilot.application.ports.audit_logger import AuditLoggerPort, AuditRecord
from contexts.insights.application.ports.baseline_repository import BaselineRecord, BaselineRepositoryPort
from contexts.insights.application.ports.feature_repository import FeatureRepositoryPort, FeatureValue
from contexts.insights.application.ports.insight_history import InsightActionItem, InsightHistoryItem, InsightHistoryPort
from contexts.insights.application.ports.insight_planner import InsightPlannerPort
from contexts.insights.application.ports.insight_repository import InsightRepositoryPort, InsightSummary
from contexts.insights.application.ports.model_runner import ModelRunnerPort
from contexts.insights.application.ports.proposal_store import ProposalStorePort, StoredProposal
from contexts.insights.application.use_cases.compute_insights import ComputeInsights
from contexts.insights.application.use_cases.get_summary import GetSummary
from contexts.insights.application.use_cases.record_action import RecordAction
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
        _ = features
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
        return [item for item in self.items if item.project_id == project_id and item.entity_id == entity_id]

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        for item in self.items:
            if item.project_id == project_id and item.id == insight_id:
                return item
        return None

    def get_summary(self, project_id: str) -> InsightSummary:
        new_items = [item for item in self.items if item.project_id == project_id and item.status == "new"]
        high = [item for item in new_items if item.severity >= 80]
        return InsightSummary(new_count_total=len(new_items), new_count_high_severity=len(high), top_insights=new_items[:3])

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        _ = (user_id, action)
        for index, item in enumerate(self.items):
            if item.id == insight_id and item.project_id == project_id:
                self.items[index] = Insight(
                    id=item.id,
                    project_id=item.project_id,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    type=item.type,
                    severity=item.severity,
                    priority=item.priority,
                    title=item.title,
                    summary=item.summary,
                    evidence=item.evidence,
                    explanations=item.explanations,
                    action=item.action,
                    model_version=item.model_version,
                    features_version=item.features_version,
                    computed_at=item.computed_at,
                    valid_until=item.valid_until,
                    status=new_status,
                    impact_min=item.impact_min,
                    impact_max=item.impact_max,
                    impact_unit=item.impact_unit,
                    confidence=item.confidence,
                    dedupe_key=item.dedupe_key,
                    cooldown_until=item.cooldown_until,
                    computed_by=item.computed_by,
                    job_run_id=item.job_run_id,
                    rules_version=item.rules_version,
                )
                return

    def get_active_by_dedupe(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        dedupe_key: str,
    ) -> Insight | None:
        for item in self.items:
            if (
                item.project_id == project_id
                and item.entity_type == entity_type
                and item.entity_id == entity_id
                and item.dedupe_key == dedupe_key
                and item.status == "new"
            ):
                return item
        return None


class FakeAuditLogger(AuditLoggerPort):
    def log(self, record: AuditRecord) -> None:
        _ = record


class FakeProposalStore(ProposalStorePort):
    def __init__(self) -> None:
        self.items: list[StoredProposal] = []

    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        ok_items = [item for item in self.items if item.insight_id == insight_id and item.status == "ok"]
        return ok_items[-1] if ok_items else None

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        all_items = [item for item in self.items if item.insight_id == insight_id]
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
        proposal_id = f"prop-{len(self.items)+1}"
        self.items.append(
            StoredProposal(
                id=proposal_id,
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
        return proposal_id


class FakePlanner(InsightPlannerPort):
    def plan(
        self,
        *,
        insight: Insight,
        historical_context: dict,
        domain: str,
        max_actions_allowed: int,
    ) -> dict:
        _ = (historical_context, domain, max_actions_allowed)
        return {
            "classification": {"severity": "high", "actionability": "act", "confidence": 0.85},
            "decision_summary": {"recommended_outcome": "propose_actions", "primary_reason": "test"},
            "proposed_plan": [
                {
                    "step": 1,
                    "action": f"Review {insight.id}",
                    "tool": "request_cost_breakdown",
                    "tool_args": {
                        "feature": "cost_total",
                        "time_window": "all",
                        "project_id": insight.project_id,
                        "insight_id": insight.id,
                    },
                    "rationale": "test",
                    "reversible": True,
                }
            ],
            "risks_and_uncertainties": [],
            "explanation": {"human_readable": "x", "audit_focused": "y", "what_to_watch_next": "z"},
        }


class FakeHistory(InsightHistoryPort):
    def get_history(self, project_id: str, entity_type: str, entity_id: str, limit: int) -> list[InsightHistoryItem]:
        _ = (project_id, entity_type, entity_id, limit)
        return []

    def get_recent_actions(self, project_id: str, limit: int) -> list[InsightActionItem]:
        _ = (project_id, limit)
        return []


class CapturingModelRunner(ModelRunnerPort):
    def __init__(self) -> None:
        self.last_features_count = 0

    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        _ = project_id
        self.last_features_count = len(features)
        return []


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
    assert result.rules_insights_created == 1


def test_compute_insights_honors_max_features() -> None:
    class ManyFeaturesRepo(FeatureRepositoryPort):
        def fetch_features(self, project_id: str) -> list[FeatureValue]:
            return [
                FeatureValue(project_id=project_id, entity_type="project", entity_id=project_id, feature_name="f1", window="all", value=1.0),
                FeatureValue(project_id=project_id, entity_type="project", entity_id=project_id, feature_name="f2", window="all", value=2.0),
                FeatureValue(project_id=project_id, entity_type="project", entity_id=project_id, feature_name="f3", window="all", value=3.0),
            ]

    model_runner = CapturingModelRunner()
    use_case = ComputeInsights(
        ManyFeaturesRepo(),
        model_runner,
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
    result = use_case.handle(project_id="p1", user_id="u1", max_features=2)
    assert result.computed == 2
    assert model_runner.last_features_count == 2


def test_compute_insights_creates_proposal_when_enabled() -> None:
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
        copilot_enabled=True,
    )
    use_case.handle(project_id="p1", user_id="u1")
    assert proposal_store.get_latest_ok("ins-1") is not None


def test_compute_insights_skips_proposal_when_copilot_disabled() -> None:
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
        copilot_enabled=False,
    )
    use_case.handle(project_id="p1", user_id="u1")
    assert proposal_store.get_latest("ins-1") is None


def test_summary_counts() -> None:
    repo = FakeInsightRepo()
    ComputeInsights(
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
    ).handle("p1", "u1")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 1
    assert summary.new_count_high_severity == 1


def test_action_updates_status() -> None:
    repo = FakeInsightRepo()
    ComputeInsights(
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
    ).handle("p1", "u1")
    RecordAction(repo, FakeAuditLogger()).handle("ins-1", "p1", "u1", "ack", "acknowledged")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 0


def test_action_missing_insight_raises_key_error() -> None:
    with pytest.raises(KeyError):
        RecordAction(FakeInsightRepo(), FakeAuditLogger()).handle("missing-id", "p1", "u1", "ack", "acknowledged")


def test_compute_insights_respects_cooldown() -> None:
    repo = FakeInsightRepo()
    now = datetime.now(timezone.utc)
    repo.items.append(
        Insight(
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
    )

    class CooldownModel(ModelRunnerPort):
        def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
            _ = features
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
        FeatureValue(project_id="p1", entity_type="project", entity_id="p1", feature_name="total_hectares", window="all", value=150),
        FeatureValue(project_id="p1", entity_type="project", entity_id="p1", feature_name="cost_total", window="all", value=40.0),
    ]
    insights = runner.compute("p1", features)
    assert len(insights) == 1
    item = insights[0]
    assert item.impact_min is not None
    assert item.impact_max is not None
    assert item.confidence == "high"
