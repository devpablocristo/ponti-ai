from adapters.outbound.sql.baseline_catalog import PROJECT_LIST_SQL
from adapters.outbound.sql.executor import SQLExecutor
from app.config import Settings
from application.insights.ports.project_repository import ProjectRepositoryPort


class ProjectRepositoryPG(ProjectRepositoryPort):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = SQLExecutor(settings)

    def list_project_ids(self, project_id: str, start_after_id: int | None, limit: int) -> list[int]:
        rows = self.executor.execute(
            sql_template=PROJECT_LIST_SQL,
            params={
                "project_id": project_id,
                "start_after_id": start_after_id,
                "limit": limit,
            },
            statement_timeout_ms=self.settings.statement_timeout_ms,
            max_limit=self.settings.max_limit,
            default_limit=self.settings.default_limit,
        )
        return [int(row["id"]) for row in rows]
