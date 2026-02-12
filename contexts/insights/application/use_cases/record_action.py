import time
import uuid

from contexts.insights.application.dto import RecordActionResult
from contexts.copilot.application.ports.audit_logger import AuditLoggerPort, AuditRecord
from contexts.insights.application.ports.insight_repository import InsightRepositoryPort

HANDLED_RECORD_ACTION_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


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
    ) -> RecordActionResult:
        request_id = str(uuid.uuid4())
        started = time.time()
        status = "ok"
        error = None
        caught_exc: Exception | None = None

        try:
            if self.insight_repo.get_by_id(project_id, insight_id) is None:
                raise KeyError("insight_not_found")
            self.insight_repo.record_action(insight_id, project_id, user_id, action, new_status)
        except HANDLED_RECORD_ACTION_ERRORS as exc:
            status = "error"
            error = str(exc)
            caught_exc = exc

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

        if caught_exc is not None:
            raise caught_exc

        return RecordActionResult(request_id=request_id)
