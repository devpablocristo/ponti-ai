import time
import uuid

from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.insights.ports.feature_repository import FeatureRepositoryPort
from application.insights.ports.insight_repository import InsightRepositoryPort
from application.insights.ports.model_runner import ModelRunnerPort


class ComputeInsights:
    def __init__(
        self,
        feature_repo: FeatureRepositoryPort,
        model_runner: ModelRunnerPort,
        insight_repo: InsightRepositoryPort,
        audit_logger: AuditLoggerPort,
    ) -> None:
        self.feature_repo = feature_repo
        self.model_runner = model_runner
        self.insight_repo = insight_repo
        self.audit_logger = audit_logger

    def handle(self, project_id: str, user_id: str) -> dict[str, int | str]:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None
        computed = 0
        created = 0

        try:
            features = self.feature_repo.fetch_features(project_id)
            computed = len(features)
            insights = self.model_runner.compute(project_id, features)
            created = self.insight_repo.upsert_many(insights)
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = str(exc)

        duration_ms = int((time.time() - started) * 1000)
        self.audit_logger.log(
            AuditRecord(
                request_id=request_id,
                user_id=user_id,
                project_id=project_id,
                question="insights_compute",
                intent="insights",
                query_id="compute",
                params={"project_id": project_id},
                duration_ms=duration_ms,
                rows_count=created,
                status=status,
                error=error,
            )
        )

        return {"request_id": request_id, "computed": computed, "insights_created": created}
