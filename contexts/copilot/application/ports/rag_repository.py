from typing import Protocol

from contexts.copilot.domain.entities import RagSearchResult


class RagRepositoryPort(Protocol):
    def ingest(self, project_id: str, documents: list[object]) -> int:
        ...

    def search(self, project_id: str, question: str) -> RagSearchResult:
        ...
