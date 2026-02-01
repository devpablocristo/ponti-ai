from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.ports.insight_repository import InsightRepositoryPort


class RecomputeActive:
    def __init__(self, compute_insights: ComputeInsights, insight_repo: InsightRepositoryPort) -> None:
        self.compute_insights = compute_insights
        self.insight_repo = insight_repo

    def handle(self, project_id: str, batch_size: int | None = None) -> None:
        _ = batch_size
        self.compute_insights.handle(project_id=project_id, user_id="scheduler")
        self.insight_repo.mark_recomputed(project_id)
