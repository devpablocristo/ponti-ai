from typing import Protocol

from application.insights.ports.feature_repository import FeatureValue
from domain.insights.entities import Insight


class MLDetectorPort(Protocol):
    def detect_anomalies(self, project_id: str, features: list[FeatureValue]) -> list[Insight]:
        ...
