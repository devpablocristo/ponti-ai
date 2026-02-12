import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from application.insights.dto import ProcessQueueItemResult, ProcessRecomputeQueueResult
from application.insights.ports.insight_repository import InsightRepositoryPort
from application.insights.ports.job_lock import JobLockPort
from application.insights.ports.recompute_queue import RecomputeQueueItem, RecomputeQueuePort
from application.insights.use_cases.compute_insights import ComputeInsights

HANDLED_PROCESS_QUEUE_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


def _project_lock_key(base_key: int, project_id: str) -> int:
    digest = hashlib.sha1(project_id.encode("utf-8")).hexdigest()[:8]
    suffix = int(digest, 16) & 0x3FFFFFFF
    return (int(base_key) & 0x3FFFFFFF) ^ suffix


class ProcessRecomputeQueue:
    def __init__(
        self,
        queue_repo: RecomputeQueuePort,
        compute_insights: ComputeInsights,
        insight_repo: InsightRepositoryPort,
        job_lock: JobLockPort,
    ) -> None:
        self.queue_repo = queue_repo
        self.compute_insights = compute_insights
        self.insight_repo = insight_repo
        self.job_lock = job_lock

    def _process_one(self, item: RecomputeQueueItem, lock_key_base: int) -> ProcessQueueItemResult:
        lock_key = _project_lock_key(lock_key_base, item.project_id)
        if not self.job_lock.try_lock(lock_key):
            self.queue_repo.mark_failed(
                project_id=item.project_id,
                error="project_locked",
                retry_after_seconds=30,
            )
            return ProcessQueueItemResult(status="locked", project_id=item.project_id)
        try:
            self.compute_insights.handle(
                project_id=item.project_id,
                user_id="event_processor",
                computed_by="event_processor",
                job_run_id=str(uuid.uuid4()),
            )
            self.insight_repo.mark_recomputed(item.project_id)
            self.queue_repo.mark_done(item.project_id)
            return ProcessQueueItemResult(status="ok", project_id=item.project_id)
        except HANDLED_PROCESS_QUEUE_ERRORS as exc:
            self.queue_repo.mark_failed(
                project_id=item.project_id,
                error=str(exc),
                retry_after_seconds=60,
            )
            return ProcessQueueItemResult(status="error", project_id=item.project_id)
        finally:
            self.job_lock.release(lock_key)

    def handle(
        self,
        limit: int,
        workers: int,
        lock_key_base: int,
        stale_lock_seconds: int = 300,
    ) -> ProcessRecomputeQueueResult:
        claimed = self.queue_repo.claim_due(
            limit=max(1, int(limit)),
            worker_id=f"worker-{uuid.uuid4()}",
            stale_after_seconds=max(30, int(stale_lock_seconds)),
        )
        if not claimed:
            return ProcessRecomputeQueueResult(claimed=0, processed=0, ok=0, locked=0, errors=0)

        max_workers = max(1, min(int(workers), len(claimed)))
        ok = 0
        locked = 0
        errors = 0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(self._process_one, item, lock_key_base) for item in claimed]
            for future in as_completed(futures):
                result = future.result()
                status = result.status
                if status == "ok":
                    ok += 1
                elif status == "locked":
                    locked += 1
                else:
                    errors += 1

        return ProcessRecomputeQueueResult(
            claimed=len(claimed),
            processed=len(claimed),
            ok=ok,
            locked=locked,
            errors=errors,
        )
