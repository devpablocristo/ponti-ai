import json

from adapters.outbound.db.session import DBSession
from application.copilot.ports.audit_logger import AuditRecord
from app.config import Settings


class AuditLoggerPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def log(self, record: AuditRecord) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_audit_logs (
                        request_id, project_id, user_id, question, intent, query_id,
                        params_json, duration_ms, rows_count, status, error, created_at
                    ) VALUES (
                        %(request_id)s, %(project_id)s, %(user_id)s, %(question)s, %(intent)s, %(query_id)s,
                        %(params_json)s, %(duration_ms)s, %(rows_count)s, %(status)s, %(error)s, NOW()
                    )
                    """,
                    {
                        "request_id": record.request_id,
                        "project_id": record.project_id,
                        "user_id": record.user_id,
                        "question": record.question,
                        "intent": record.intent,
                        "query_id": record.query_id,
                        "params_json": json.dumps(record.params),
                        "duration_ms": record.duration_ms,
                        "rows_count": record.rows_count,
                        "status": record.status,
                        "error": record.error,
                    },
                )
            conn.commit()
