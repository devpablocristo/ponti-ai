from adapters.outbound.db.session import DBSession
from app.config import Settings
from application.copilot.ports.insight_reader import InsightReaderPort, RelatedInsight


class InsightReaderPG(InsightReaderPort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def count_active(self, project_id: str) -> int:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND status = 'new'
                      AND valid_until >= NOW()
                    """,
                    {"project_id": project_id},
                )
                return int(cur.fetchone()["total"])

    def list_active(self, project_id: str, limit: int) -> list[RelatedInsight]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, entity_type, entity_id, title
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND status = 'new'
                      AND valid_until >= NOW()
                    ORDER BY severity DESC, computed_at DESC
                    LIMIT %(limit)s
                    """,
                    {"project_id": project_id, "limit": limit},
                )
                rows = cur.fetchall()
        return [
            RelatedInsight(
                id=row["id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                title=row["title"],
            )
            for row in rows
        ]
