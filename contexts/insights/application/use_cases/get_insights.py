from contexts.insights.application.ports.insight_repository import InsightRepositoryPort
from contexts.insights.domain.entities import Insight


class GetInsights:
    def __init__(self, insight_repo: InsightRepositoryPort) -> None:
        self.insight_repo = insight_repo

    def handle(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        return self.insight_repo.get_by_entity(project_id, entity_type, entity_id)
