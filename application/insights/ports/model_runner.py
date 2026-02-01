from typing import Protocol

from application.insights.ports.feature_repository import FeatureValue
from domain.insights.entities import Insight


class ModelRunnerPort(Protocol):
    def compute(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        ...
