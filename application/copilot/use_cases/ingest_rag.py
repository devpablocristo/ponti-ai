from application.copilot.ports.rag_repository import RagRepositoryPort


class IngestRag:
    def __init__(self, rag_repo: RagRepositoryPort) -> None:
        self.rag_repo = rag_repo

    def handle(self, project_id: str, documents: list[object]) -> int:
        return self.rag_repo.ingest(project_id, documents)
