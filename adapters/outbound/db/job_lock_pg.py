from adapters.outbound.db.session import DBSession
from app.config import Settings
from contexts.insights.application.ports.job_lock import JobLockPort


class JobLockPG(JobLockPort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def try_lock(self, key: int) -> bool:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s) AS locked", (key,))
                row = cur.fetchone()
                return bool(row["locked"])

    def release(self, key: int) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (key,))
