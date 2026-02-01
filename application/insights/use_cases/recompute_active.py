import uuid

from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.ports.insight_repository import InsightRepositoryPort
from application.insights.ports.job_lock import JobLockPort


class RecomputeActive:
    def __init__(
        self,
        compute_insights: ComputeInsights,
        insight_repo: InsightRepositoryPort,
        job_lock: JobLockPort,
    ) -> None:
        self.compute_insights = compute_insights
        self.insight_repo = insight_repo
        self.job_lock = job_lock

    def handle(self, project_id: str, lock_key: int, batch_size: int | None = None) -> dict[str, str]:
        _ = batch_size
        if not self.job_lock.try_lock(lock_key):
            return {"status": "locked", "job_run_id": ""}
        job_run_id = str(uuid.uuid4())
        try:
            self.compute_insights.handle(project_id=project_id, user_id="scheduler")
            self.insight_repo.mark_recomputed(project_id)
        finally:
            self.job_lock.release(lock_key)
        return {"status": "ok", "job_run_id": job_run_id}
