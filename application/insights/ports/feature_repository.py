from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FeatureValue:
    project_id: str
    entity_type: str
    entity_id: str
    feature_name: str
    value: float


class FeatureRepositoryPort(Protocol):
    def fetch_features(self, project_id: str) -> list[FeatureValue]:
        ...
