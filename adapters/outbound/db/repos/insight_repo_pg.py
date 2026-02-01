import json
import uuid
from datetime import datetime

from adapters.outbound.db.session import DBSession
from application.insights.ports.insight_repository import InsightRepositoryPort, InsightSummary
from app.config import Settings
from domain.insights.entities import Insight


def _row_to_insight(row: dict) -> Insight:
    return Insight(
        id=row["id"],
        project_id=row["project_id"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        type=row["type"],
        severity=row["severity"],
        priority=row["priority"],
        title=row["title"],
        summary=row["summary"],
        evidence=row.get("evidence_json", {}) or {},
        explanations=row.get("explanations_json", {}) or {},
        action=row.get("action_json", {}) or {},
        model_version=row["model_version"],
        features_version=row["features_version"],
        computed_at=row["computed_at"],
        valid_until=row["valid_until"],
        status=row["status"],
    )


class InsightRepositoryPG(InsightRepositoryPort):
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def upsert_many(self, insights: list[Insight]) -> int:
        if not insights:
            return 0
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                for insight in insights:
                    cur.execute(
                        """
                        INSERT INTO ai_insights (
                            id, project_id, entity_type, entity_id, type, severity, priority,
                            title, summary, evidence_json, explanations_json, action_json,
                            model_version, features_version, computed_at, valid_until, status
                        ) VALUES (
                            %(id)s, %(project_id)s, %(entity_type)s, %(entity_id)s, %(type)s, %(severity)s, %(priority)s,
                            %(title)s, %(summary)s, %(evidence_json)s, %(explanations_json)s, %(action_json)s,
                            %(model_version)s, %(features_version)s, %(computed_at)s, %(valid_until)s, %(status)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            severity = EXCLUDED.severity,
                            priority = EXCLUDED.priority,
                            summary = EXCLUDED.summary,
                            evidence_json = EXCLUDED.evidence_json,
                            explanations_json = EXCLUDED.explanations_json,
                            action_json = EXCLUDED.action_json,
                            valid_until = EXCLUDED.valid_until,
                            status = EXCLUDED.status
                        """,
                        {
                            "id": insight.id,
                            "project_id": insight.project_id,
                            "entity_type": insight.entity_type,
                            "entity_id": insight.entity_id,
                            "type": insight.type,
                            "severity": insight.severity,
                            "priority": insight.priority,
                            "title": insight.title,
                            "summary": insight.summary,
                            "evidence_json": json.dumps(insight.evidence),
                            "explanations_json": json.dumps(insight.explanations),
                            "action_json": json.dumps(insight.action),
                            "model_version": insight.model_version,
                            "features_version": insight.features_version,
                            "computed_at": insight.computed_at,
                            "valid_until": insight.valid_until,
                            "status": insight.status,
                        },
                    )
            conn.commit()
        return len(insights)

    def get_by_entity(self, project_id: str, entity_type: str, entity_id: str) -> list[Insight]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND entity_type = %(entity_type)s
                      AND entity_id = %(entity_id)s
                    ORDER BY computed_at DESC
                    """,
                    {"project_id": project_id, "entity_type": entity_type, "entity_id": entity_id},
                )
                rows = cur.fetchall()
        return [_row_to_insight(dict(row)) for row in rows]

    def get_summary(self, project_id: str) -> InsightSummary:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM ai_insights
                    WHERE project_id = %(project_id)s AND status = 'new'
                    """,
                    {"project_id": project_id},
                )
                total = int(cur.fetchone()["total"])
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM ai_insights
                    WHERE project_id = %(project_id)s AND status = 'new' AND severity >= 80
                    """,
                    {"project_id": project_id},
                )
                high = int(cur.fetchone()["total"])
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                    ORDER BY severity DESC, computed_at DESC
                    LIMIT 3
                    """,
                    {"project_id": project_id},
                )
                rows = cur.fetchall()

        top_insights = [_row_to_insight(dict(row)) for row in rows]
        return InsightSummary(new_count_total=total, new_count_high_severity=high, top_insights=top_insights)

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_insight_actions (id, insight_id, project_id, user_id, action, created_at)
                    VALUES (%(id)s, %(insight_id)s, %(project_id)s, %(user_id)s, %(action)s, NOW())
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "insight_id": insight_id,
                        "project_id": project_id,
                        "user_id": user_id,
                        "action": action,
                    },
                )
                cur.execute(
                    """
                    UPDATE ai_insights
                    SET status = %(status)s
                    WHERE id = %(insight_id)s AND project_id = %(project_id)s
                    """,
                    {"status": new_status, "insight_id": insight_id, "project_id": project_id},
                )
            conn.commit()

    def mark_recomputed(self, project_id: str) -> None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ai_insights
                    SET computed_at = NOW()
                    WHERE project_id = %(project_id)s
                    """,
                    {"project_id": project_id},
                )
            conn.commit()
