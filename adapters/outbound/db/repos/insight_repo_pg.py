import json
import uuid

from adapters.outbound.db.session import DBSession
from contexts.insights.application.ports.insight_repository import InsightRepositoryPort, InsightSummary
from app.config import Settings
from contexts.insights.domain.entities import Insight


def _row_to_insight(row: dict) -> Insight:
    return Insight(
        id=str(row["id"]),
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
        impact_min=row.get("impact_min"),
        impact_max=row.get("impact_max"),
        impact_unit=row.get("impact_unit"),
        confidence=row.get("confidence"),
        dedupe_key=row.get("dedupe_key"),
        cooldown_until=row.get("cooldown_until"),
        computed_by=row.get("computed_by", "on_demand"),
        job_run_id=row.get("job_run_id"),
        rules_version=row.get("rules_version", "v1"),
    )


def _parse_uuid_or_none(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return None


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
                            model_version, features_version, computed_at, valid_until, status,
                            impact_min, impact_max, impact_unit, confidence,
                            dedupe_key, cooldown_until, computed_by, job_run_id, rules_version
                        ) VALUES (
                            %(id)s, %(project_id)s, %(entity_type)s, %(entity_id)s, %(type)s, %(severity)s, %(priority)s,
                            %(title)s, %(summary)s, %(evidence_json)s, %(explanations_json)s, %(action_json)s,
                            %(model_version)s, %(features_version)s, %(computed_at)s, %(valid_until)s, %(status)s,
                            %(impact_min)s, %(impact_max)s, %(impact_unit)s, %(confidence)s,
                            %(dedupe_key)s, %(cooldown_until)s, %(computed_by)s, %(job_run_id)s, %(rules_version)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            severity = EXCLUDED.severity,
                            priority = EXCLUDED.priority,
                            summary = EXCLUDED.summary,
                            evidence_json = EXCLUDED.evidence_json,
                            explanations_json = EXCLUDED.explanations_json,
                            action_json = EXCLUDED.action_json,
                            valid_until = EXCLUDED.valid_until,
                            status = EXCLUDED.status,
                            impact_min = EXCLUDED.impact_min,
                            impact_max = EXCLUDED.impact_max,
                            impact_unit = EXCLUDED.impact_unit,
                            confidence = EXCLUDED.confidence,
                            dedupe_key = EXCLUDED.dedupe_key,
                            cooldown_until = EXCLUDED.cooldown_until,
                            computed_by = EXCLUDED.computed_by,
                            job_run_id = EXCLUDED.job_run_id,
                            rules_version = EXCLUDED.rules_version
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
                            "impact_min": insight.impact_min,
                            "impact_max": insight.impact_max,
                            "impact_unit": insight.impact_unit,
                            "confidence": insight.confidence,
                            "dedupe_key": insight.dedupe_key,
                            "cooldown_until": insight.cooldown_until,
                            "computed_by": insight.computed_by,
                            "job_run_id": insight.job_run_id,
                            "rules_version": insight.rules_version,
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
                      AND status <> 'shadow'
                    ORDER BY computed_at DESC
                    """,
                    {"project_id": project_id, "entity_type": entity_type, "entity_id": entity_id},
                )
                rows = cur.fetchall()
        return [_row_to_insight(dict(row)) for row in rows]

    def get_by_id(self, project_id: str, insight_id: str) -> Insight | None:
        parsed_id = _parse_uuid_or_none(insight_id)
        if parsed_id is None:
            return None
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND id = %(insight_id)s::uuid
                    LIMIT 1
                    """,
                    {"project_id": project_id, "insight_id": str(parsed_id)},
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_insight(dict(row))

    def get_summary(self, project_id: str) -> InsightSummary:
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
                total = int(cur.fetchone()["total"])
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND status = 'new'
                      AND severity >= 80
                      AND valid_until >= NOW()
                    """,
                    {"project_id": project_id},
                )
                high = int(cur.fetchone()["total"])
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND status = 'new'
                      AND valid_until >= NOW()
                    ORDER BY severity DESC, computed_at DESC
                    LIMIT 3
                    """,
                    {"project_id": project_id},
                )
                rows = cur.fetchall()

        top_insights = [_row_to_insight(dict(row)) for row in rows]
        return InsightSummary(new_count_total=total, new_count_high_severity=high, top_insights=top_insights)

    def record_action(self, insight_id: str, project_id: str, user_id: str, action: str, new_status: str) -> None:
        parsed_id = _parse_uuid_or_none(insight_id)
        if parsed_id is None:
            raise ValueError("insight_id_invalido")
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_insight_actions (id, insight_id, project_id, user_id, action, created_at)
                    VALUES (%(id)s, %(insight_id)s, %(project_id)s, %(user_id)s, %(action)s, NOW())
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "insight_id": str(parsed_id),
                        "project_id": project_id,
                        "user_id": user_id,
                        "action": action,
                    },
                )
                cur.execute(
                    """
                    UPDATE ai_insights
                    SET status = %(status)s
                    WHERE id = %(insight_id)s::uuid AND project_id = %(project_id)s
                    """,
                    {"status": new_status, "insight_id": str(parsed_id), "project_id": project_id},
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

    def get_active_by_dedupe(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        dedupe_key: str,
    ) -> Insight | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM ai_insights
                    WHERE project_id = %(project_id)s
                      AND entity_type = %(entity_type)s
                      AND entity_id = %(entity_id)s
                      AND dedupe_key = %(dedupe_key)s
                      AND status = 'new'
                      AND valid_until >= NOW()
                    ORDER BY computed_at DESC
                    LIMIT 1
                    """,
                    {
                        "project_id": project_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "dedupe_key": dedupe_key,
                    },
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_insight(dict(row))

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

    def list_active(self, project_id: str, limit: int) -> list[Insight]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
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
        return [_row_to_insight(dict(row)) for row in rows]
