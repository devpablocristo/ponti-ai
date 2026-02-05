from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class InsightHistoryItem:
    id: str
    type: str
    severity: int
    status: str
    computed_at: datetime
    title: str


@dataclass(frozen=True)
class InsightActionItem:
    insight_id: str
    user_id: str
    action: str
    created_at: datetime


class InsightHistoryPort(Protocol):
    def get_history(self, project_id: str, entity_type: str, entity_id: str, limit: int) -> list[InsightHistoryItem]:
        ...

    def get_recent_actions(self, project_id: str, limit: int) -> list[InsightActionItem]:
        ...

