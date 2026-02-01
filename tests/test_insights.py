from datetime import datetime, timedelta, timezone

from application.insights.ports.feature_repository import FeatureRepositoryPort, FeatureValue
from application.insights.ports.insight_repository import InsightRepositoryPort, InsightSummary
from application.insights.ports.model_runner import ModelRunnerPort
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
                )
                return

    def mark_recomputed(self, project_id: str) -> None:
        return None


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
