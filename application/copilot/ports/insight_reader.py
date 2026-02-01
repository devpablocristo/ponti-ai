from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RelatedInsight:
    id: str
    entity_type: str
    entity_id: str
    title: str


class InsightReaderPort(Protocol):
    def count_active(self, project_id: str) -> int:
        ...

    def list_active(self, project_id: str, limit: int) -> list[RelatedInsight]:
        ...
