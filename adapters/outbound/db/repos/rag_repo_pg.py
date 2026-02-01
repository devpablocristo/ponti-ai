from adapters.outbound.rag.ingest import ingest_documents
from adapters.outbound.rag.search import search_documents
from app.config import Settings
from domain.copilot.entities import RagSearchResult


class RagRepositoryPG:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ingest(self, project_id: str, documents: list[object]) -> int:
        return ingest_documents(self.settings, project_id, documents)

    def search(self, project_id: str, question: str) -> RagSearchResult:
        return search_documents(self.settings, project_id, question)
