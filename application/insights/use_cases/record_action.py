import time
import uuid

from application.copilot.ports.audit_logger import AuditLoggerPort, AuditRecord
from application.insights.ports.insight_repository import InsightRepositoryPort


class RecordAction:
    def __init__(self, insight_repo: InsightRepositoryPort, audit_logger: AuditLoggerPort) -> None:
        self.insight_repo = insight_repo
        self.audit_logger = audit_logger

    def handle(
        self,
        insight_id: str,
        project_id: str,
        user_id: str,
        action: str,
        new_status: str,
    ) -> dict[str, str]:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None

        try:
            self.insight_repo.record_action(insight_id, project_id, user_id, action, new_status)
        except Exception as exc:  # noqa: BLE001
            status = "error"
            error = str(exc)

        duration_ms = int((time.time() - started) * 1000)
        self.audit_logger.log(
            AuditRecord(
                request_id=request_id,
                user_id=user_id,
                project_id=project_id,
                question="insight_action",
                intent="insights",
                query_id="action",
                params={"insight_id": insight_id, "action": action, "new_status": new_status},
                duration_ms=duration_ms,
                rows_count=1,
                status=status,
                error=error,
            )
        )

        return {"request_id": request_id}
