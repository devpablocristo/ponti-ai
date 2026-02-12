from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BaselineRecord:
    scope_type: str
    scope_id: str | None
    cohort_key: str
    feature_name: str
    window: str
    p50: float
    p75: float
    p90: float
    n_samples: int
    computed_at: datetime


class BaselineRepositoryPort(Protocol):
    def upsert_many(self, records: list[BaselineRecord]) -> int:
        ...

    def get_baseline(
        self,
        scope_type: str,
        scope_id: str | None,
        cohort_key: str,
        feature_name: str,
        window: str,
    ) -> BaselineRecord | None:
        ...
