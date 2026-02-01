from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AuditRecord:
    request_id: str
    user_id: str
    project_id: str
    question: str
    intent: str
    query_id: str | None
    params: dict
    duration_ms: int
    rows_count: int
    status: str
    error: str | None


class AuditLoggerPort(Protocol):
    def log(self, record: AuditRecord) -> None:
        ...
