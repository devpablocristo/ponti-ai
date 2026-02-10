from datetime import timedelta

from adapters.outbound.db.session import DBSession
from app.config import Settings
from application.insights.ports.recompute_queue import RecomputeQueueItem, RecomputeQueuePort


class RecomputeQueuePG(RecomputeQueuePort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def enqueue_event(
        self,
        project_id: str,
        source: str,
        reason: str | None,
        debounce_seconds: int,
    ) -> dict[str, str]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_recompute_queue (
                        project_id,
                        source,
                        reason,
                        status,
                        first_seen_at,
                        last_seen_at,
                        next_run_at,
                        attempt_count,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        %(project_id)s,
                        %(source)s,
                        %(reason)s,
                        'queued',
                        NOW(),
                        NOW(),
                        NOW() + (%(debounce_seconds)s * INTERVAL '1 second'),
                        0,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (project_id) DO UPDATE SET
                        source = EXCLUDED.source,
                        reason = EXCLUDED.reason,
                        status = 'queued',
                        last_seen_at = NOW(),
                        next_run_at = NOW() + (%(debounce_seconds)s * INTERVAL '1 second'),
                        updated_at = NOW(),
                        locked_by = NULL,
                        locked_at = NULL
                    """,
                    {
                        "project_id": project_id,
                        "source": source,
                        "reason": reason,
                        "debounce_seconds": debounce_seconds,
                    },
                )
            conn.commit()
        return {"status": "queued", "project_id": project_id}

    def claim_due(
        self,
        limit: int,
        worker_id: str,
        stale_after_seconds: int = 300,
    ) -> list[RecomputeQueueItem]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH due AS (
                        SELECT project_id
                        FROM ai_recompute_queue
                        WHERE
                            (
                                status = 'queued'
                                AND next_run_at <= NOW()
                            )
                            OR (
                                status = 'processing'
                                AND locked_at <= NOW() - (%(stale_after_seconds)s * INTERVAL '1 second')
                            )
                        ORDER BY next_run_at ASC
                        LIMIT %(limit)s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE ai_recompute_queue q
                    SET
                        status = 'processing',
                        locked_by = %(worker_id)s,
                        locked_at = NOW(),
                        attempt_count = q.attempt_count + 1,
                        updated_at = NOW()
                    FROM due
                    WHERE q.project_id = due.project_id
                    RETURNING q.project_id, q.reason, q.source, q.last_seen_at, q.attempt_count
                    """,
                    {
                        "limit": max(1, int(limit)),
                        "worker_id": worker_id,
                        "stale_after_seconds": max(30, int(stale_after_seconds)),
                    },
                )
                rows = cur.fetchall()
            conn.commit()
        return [
            RecomputeQueueItem(
                project_id=str(row["project_id"]),
                reason=row.get("reason"),
                source=str(row.get("source") or "event"),
                last_seen_at=row["last_seen_at"],
                attempts=int(row.get("attempt_count") or 0),
            )
            for row in rows
        ]

    def mark_done(self, project_id: str) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ai_recompute_queue
                    SET
                        status = 'idle',
                        last_error = NULL,
                        next_run_at = NULL,
                        locked_by = NULL,
                        locked_at = NULL,
                        updated_at = NOW()
                    WHERE project_id = %(project_id)s
                    """,
                    {"project_id": project_id},
                )
            conn.commit()

    def mark_failed(self, project_id: str, error: str, retry_after_seconds: int = 60) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ai_recompute_queue
                    SET
                        status = 'queued',
                        last_error = %(error)s,
                        next_run_at = NOW() + (%(retry_after_seconds)s * INTERVAL '1 second'),
                        locked_by = NULL,
                        locked_at = NULL,
                        updated_at = NOW()
                    WHERE project_id = %(project_id)s
                    """,
                    {
                        "project_id": project_id,
                        "error": (error or "")[:1000],
                        "retry_after_seconds": max(5, int(retry_after_seconds)),
                    },
                )
            conn.commit()
