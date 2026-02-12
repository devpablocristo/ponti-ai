import uuid

from application.insights.dto import RecomputeBaselinesResult
from application.insights.ports.baseline_computer import BaselineComputerPort, CohortConfig
from application.insights.ports.baseline_repository import BaselineRepositoryPort
from application.insights.ports.job_lock import JobLockPort
from application.insights.ports.project_repository import ProjectRepositoryPort


class RecomputeBaselines:
    def __init__(
        self,
        baseline_computer: BaselineComputerPort,
        baseline_repo: BaselineRepositoryPort,
        project_repo: ProjectRepositoryPort,
        job_lock: JobLockPort,
    ) -> None:
        self.baseline_computer = baseline_computer
        self.baseline_repo = baseline_repo
        self.project_repo = project_repo
        self.job_lock = job_lock

    def handle(
        self,
        project_id: str,
        cohort: CohortConfig,
        baseline_days: int,
        min_samples: int,
        batch_size: int,
        lock_key: int,
    ) -> RecomputeBaselinesResult:
        if not self.job_lock.try_lock(lock_key):
            return RecomputeBaselinesResult(status="locked", job_run_id="", cohort_saved=0, project_saved=0)

        job_run_id = str(uuid.uuid4())
        cohort_saved = 0
        project_saved = 0
        try:
            cohort_records = self.baseline_computer.compute_cohort_baselines(project_id, cohort)
            cohort_saved = self.baseline_repo.upsert_many(cohort_records)

            last_id: int | None = None
            while True:
                ids = self.project_repo.list_project_ids(project_id, last_id, batch_size)
                if not ids:
                    break
                for pid in ids:
                    records = self.baseline_computer.compute_project_baselines(
                        project_id=str(pid),
                        baseline_days=baseline_days,
                        min_samples=min_samples,
                    )
                    project_saved += self.baseline_repo.upsert_many(records)
                last_id = ids[-1]
        finally:
            self.job_lock.release(lock_key)

        return RecomputeBaselinesResult(
            status="ok",
            job_run_id=job_run_id,
            cohort_saved=cohort_saved,
            project_saved=project_saved,
        )
