from adapters.outbound.db.session import DBSession
from app.config import Settings
from contexts.insights.application.ports.insight_history import InsightActionItem, InsightHistoryItem, InsightHistoryPort


class InsightHistoryPG(InsightHistoryPort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_history(self, project_id: str, entity_type: str, entity_id: str, limit: int) -> list[InsightHistoryItem]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, type, severity, status, computed_at, title
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND entity_type = %(entity_type)s
                      AND entity_id = %(entity_id)s
                    ORDER BY computed_at DESC
                    LIMIT %(limit)s
                    """,
                    {
                        "project_id": project_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "limit": limit,
                    },
                )
                rows = cur.fetchall()
        return [
            InsightHistoryItem(
                id=str(r["id"]),
                type=str(r["type"]),
                severity=int(r["severity"]),
                status=str(r["status"]),
                computed_at=r["computed_at"],
                title=str(r["title"]),
            )
            for r in rows
        ]

    def get_recent_actions(self, project_id: str, limit: int) -> list[InsightActionItem]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT insight_id, user_id, action, created_at
                    FROM ai_insight_actions
                    WHERE project_id = %(project_id)s
                    ORDER BY created_at DESC
                    LIMIT %(limit)s
                    """,
                    {"project_id": project_id, "limit": limit},
                )
                rows = cur.fetchall()
        return [
            InsightActionItem(
                insight_id=str(r["insight_id"]),
                user_id=str(r["user_id"]),
                action=str(r["action"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

