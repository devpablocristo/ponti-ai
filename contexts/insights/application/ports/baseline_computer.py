from dataclasses import dataclass
from typing import Protocol

from contexts.insights.application.ports.baseline_repository import BaselineRecord


@dataclass(frozen=True)
class CohortConfig:
    size_small_max: float
    size_medium_max: float


class BaselineComputerPort(Protocol):
    def compute_cohort_baselines(
        self,
        project_id: str,
        cohort: CohortConfig,
    ) -> list[BaselineRecord]:
        ...

    def compute_project_baselines(
        self,
        project_id: str,
        baseline_days: int,
        min_samples: int,
    ) -> list[BaselineRecord]:
        ...
