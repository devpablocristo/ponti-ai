from dataclasses import dataclass


@dataclass(frozen=True)
class EntityRef:
    entity_type: str
    entity_id: str
