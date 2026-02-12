from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RecomputeQueueItem:
    project_id: str
    reason: str | None
    source: str
    last_seen_at: datetime
    attempts: int


class RecomputeQueuePort(Protocol):
    def enqueue_event(
        self,
        project_id: str,
        source: str,
        reason: str | None,
        debounce_seconds: int,
    ) -> dict[str, str]:
        ...

    def claim_due(
        self,
        limit: int,
        worker_id: str,
        stale_after_seconds: int = 300,
    ) -> list[RecomputeQueueItem]:
        ...

    def mark_done(self, project_id: str) -> None:
        ...

    def mark_failed(self, project_id: str, error: str, retry_after_seconds: int = 60) -> None:
        ...
