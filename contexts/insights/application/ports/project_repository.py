from typing import Protocol


class ProjectRepositoryPort(Protocol):
    def list_project_ids(self, project_id: str, start_after_id: int | None, limit: int) -> list[int]:
        ...
