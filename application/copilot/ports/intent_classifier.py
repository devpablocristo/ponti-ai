from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    query_id: str | None
    params: dict[str, Any]


class IntentClassifierPort(Protocol):
    def classify(self, question: str, params: dict[str, Any]) -> IntentDecision:
        ...
