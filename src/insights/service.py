"""Use case mínimo de insights: solo summary (consumido por dossier del chat)."""

from __future__ import annotations

from src.insights.domain import InsightSummary


class GetSummary:
    def __init__(self, insight_repo) -> None:
        self.insight_repo = insight_repo

    def handle(self, project_id: str) -> InsightSummary:
        return self.insight_repo.get_summary(project_id)
