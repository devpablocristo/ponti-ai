from datetime import datetime, timedelta, timezone

from application.insights.ports.feature_repository import FeatureRepositoryPort, FeatureValue
from application.insights.ports.insight_repository import InsightRepositoryPort, InsightSummary
from application.insights.ports.model_runner import ModelRunnerPort
from application.insights.ports.baseline_repository import BaselineRecord, BaselineRepositoryPort
from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.use_cases.get_summary import GetSummary
from application.insights.use_cases.record_action import RecordAction
from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from domain.insights.entities import Insight


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
                evidence={"feature": "cost_total"},
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


def test_compute_insights_creates_records() -> None:
    use_case = ComputeInsights(FakeFeatureRepo(), FakeModelRunner(), FakeInsightRepo(), FakeAuditLogger())
    result = use_case.handle(project_id="p1", user_id="u1")
    assert result["insights_created"] == 1


def test_summary_counts() -> None:
    repo = FakeInsightRepo()
    model = FakeModelRunner()
    features = FakeFeatureRepo()
    ComputeInsights(features, model, repo, FakeAuditLogger()).handle("p1", "u1")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 1
    assert summary.new_count_high_severity == 1


def test_action_updates_status() -> None:
    repo = FakeInsightRepo()
    model = FakeModelRunner()
    features = FakeFeatureRepo()
    ComputeInsights(features, model, repo, FakeAuditLogger()).handle("p1", "u1")
    RecordAction(repo, FakeAuditLogger()).handle("ins-1", "p1", "u1", "ignored", "ignored")
    summary = GetSummary(repo).handle("p1")
    assert summary.new_count_total == 0


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

    result = ComputeInsights(FakeFeatureRepo(), CooldownModel(), repo, FakeAuditLogger()).handle("p1", "u1")
    assert result["insights_created"] == 0


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
