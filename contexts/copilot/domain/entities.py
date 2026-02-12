from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RagSearchResult:
    doc_ids: list[str]
    top_k: int
    answer: str
    payload: dict[str, Any] | None = None
