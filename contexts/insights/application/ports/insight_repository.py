from dataclasses import dataclass
from typing import Protocol

from contexts.insights.domain.entities import Insight


@dataclass(frozen=True)
class InsightSummary:
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[Insight]


class InsightRepositoryPort(Protocol):
    def upsert_many(self, insights: list[Insight]) -> int:
        ...

    def get_by_entity(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        ...

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        ...

    def get_summary(self, project_id: str) -> InsightSummary:
        ...

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        ...

    def get_active_by_dedupe(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        dedupe_key: str,
    ) -> Insight | None:
        ...
