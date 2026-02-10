from application.insights.ports.recompute_queue import RecomputeQueuePort


class QueueRecomputeEvent:
    def __init__(self, queue_repo: RecomputeQueuePort) -> None:
        self.queue_repo = queue_repo

    def handle(
        self,
        project_id: str,
        source: str,
        reason: str | None,
        debounce_seconds: int,
    ) -> dict[str, str]:
        return self.queue_repo.enqueue_event(
            project_id=project_id,
            source=source,
            reason=reason,
            debounce_seconds=debounce_seconds,
        )
