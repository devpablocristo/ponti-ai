from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Insight:
    id: str
    project_id: str
    entity_type: str
    entity_id: str
    type: str
    severity: int
    priority: int
    title: str
    summary: str
    evidence: dict[str, Any]
    explanations: dict[str, Any]
    action: dict[str, Any]
    model_version: str
    features_version: str
    computed_at: datetime
    valid_until: datetime
    status: str
