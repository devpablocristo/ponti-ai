from application.insights.ports.insight_repository import InsightRepositoryPort, InsightSummary


class GetSummary:
    def __init__(self, insight_repo: InsightRepositoryPort) -> None:
        self.insight_repo = insight_repo

    def handle(self, project_id: str) -> InsightSummary:
        return self.insight_repo.get_summary(project_id)
