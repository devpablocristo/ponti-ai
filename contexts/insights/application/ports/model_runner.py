from typing import Protocol

from contexts.insights.application.ports.feature_repository import FeatureValue
from contexts.insights.domain.entities import Insight


class ModelRunnerPort(Protocol):
    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        ...
