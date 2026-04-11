"""Repositorios PostgreSQL para el dominio de insights."""

from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg
from runtime.logging import get_logger

from src.config import Settings
from src.db.session import DBSession
from src.insights.domain import (
    AuditRecord,
    BaselineRecord,
    FeatureValue,
    Insight,
    InsightActionItem,
    InsightHistoryItem,
    InsightSummary,
    StoredProposal,
)

HANDLED_DB_ERRORS = (psycopg.Error, ValueError, OSError)
logger = get_logger(__name__)


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


class InsightRepositoryPG:
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
                    SELECT * FROM ai_insights
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
                    SELECT * FROM ai_insights
                    WHERE project_id = %(project_id)s AND id = %(insight_id)s::uuid
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
                    "SELECT COUNT(*) AS total FROM ai_insights WHERE project_id = %(pid)s AND status = 'new' AND valid_until >= NOW()",
                    {"pid": project_id},
                )
                total = int(cur.fetchone()["total"])
                cur.execute(
                    "SELECT COUNT(*) AS total FROM ai_insights WHERE project_id = %(pid)s AND status = 'new' AND severity >= 80 AND valid_until >= NOW()",
                    {"pid": project_id},
                )
                high = int(cur.fetchone()["total"])
                cur.execute(
                    """
                    SELECT * FROM ai_insights
                    WHERE project_id = %(pid)s AND status = 'new' AND valid_until >= NOW()
                    ORDER BY severity DESC, computed_at DESC LIMIT 20
                    """,
                    {"pid": project_id},
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
                    {"id": str(uuid.uuid4()), "insight_id": str(parsed_id), "project_id": project_id, "user_id": user_id, "action": action},
                )
                cur.execute(
                    "UPDATE ai_insights SET status = %(status)s WHERE id = %(insight_id)s::uuid AND project_id = %(project_id)s",
                    {"status": new_status, "insight_id": str(parsed_id), "project_id": project_id},
                )
            conn.commit()

    def get_active_by_dedupe(self, project_id: str, entity_type: str, entity_id: str, dedupe_key: str) -> Insight | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM ai_insights
                    WHERE project_id = %(project_id)s AND entity_type = %(entity_type)s
                      AND entity_id = %(entity_id)s AND dedupe_key = %(dedupe_key)s
                      AND status = 'new' AND valid_until >= NOW()
                    ORDER BY computed_at DESC LIMIT 1
                    """,
                    {"project_id": project_id, "entity_type": entity_type, "entity_id": entity_id, "dedupe_key": dedupe_key},
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_insight(dict(row))


class FeatureRepositoryPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def fetch_features(self, project_id: str) -> list[FeatureValue]:
        try:
            with self.session.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM ai_features WHERE project_id = %(project_id)s",
                        {"project_id": project_id},
                    )
                    rows = cur.fetchall()
            return [
                FeatureValue(
                    project_id=str(row["project_id"]),
                    entity_type=str(row["entity_type"]),
                    entity_id=str(row["entity_id"]),
                    feature_name=str(row["feature_name"]),
                    window=str(row["window"]),
                    value=float(row["value"]),
                )
                for row in rows
            ]
        except HANDLED_DB_ERRORS:
            return []


class AuditLoggerPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def log(self, record: AuditRecord) -> None:
        try:
            with self.session.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                            INSERT INTO ai_audit_logs (
                                request_id, user_id, project_id, question, intent,
                                query_id, params_json, duration_ms, rows_count, status, error, created_at
                            ) VALUES (
                                %(request_id)s, %(user_id)s, %(project_id)s, %(question)s, %(intent)s,
                                %(query_id)s, %(params_json)s::jsonb, %(duration_ms)s, %(rows_count)s, %(status)s, %(error)s, NOW()
                            )
                            """,
                        {
                                "request_id": record.request_id,
                                "user_id": record.user_id,
                                "project_id": record.project_id,
                                "question": record.question,
                                "intent": record.intent,
                                "query_id": record.query_id,
                                "params_json": json.dumps(record.params),
                                "duration_ms": record.duration_ms,
                                "rows_count": record.rows_count,
                                "status": record.status,
                                "error": record.error,
                            },
                        )
                conn.commit()
        except HANDLED_DB_ERRORS as exc:
            logger.warning(
                "ai_audit_log_persist_failed",
                request_id=record.request_id,
                project_id=record.project_id,
                error=str(exc),
            )


class BaselineRepositoryPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def upsert_many(self, records: list[BaselineRecord]) -> int:
        if not records:
            return 0
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                for rec in records:
                    stable_id = f"{rec.scope_type}:{rec.scope_id}:{rec.cohort_key}:{rec.feature_name}:{rec.window}"
                    cur.execute(
                        """
                        INSERT INTO ai_baselines (
                            id, scope_type, scope_id, cohort_key, feature_name, window,
                            p50, p75, p90, n_samples, computed_at
                        ) VALUES (
                            %(id)s, %(scope_type)s, %(scope_id)s, %(cohort_key)s, %(feature_name)s, %(window)s,
                            %(p50)s, %(p75)s, %(p90)s, %(n_samples)s, %(computed_at)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            p50 = EXCLUDED.p50, p75 = EXCLUDED.p75, p90 = EXCLUDED.p90,
                            n_samples = EXCLUDED.n_samples, computed_at = EXCLUDED.computed_at
                        """,
                        {
                            "id": stable_id,
                            "scope_type": rec.scope_type,
                            "scope_id": rec.scope_id,
                            "cohort_key": rec.cohort_key,
                            "feature_name": rec.feature_name,
                            "window": rec.window,
                            "p50": rec.p50,
                            "p75": rec.p75,
                            "p90": rec.p90,
                            "n_samples": rec.n_samples,
                            "computed_at": rec.computed_at,
                        },
                    )
            conn.commit()
        return len(records)

    def get_baseline(self, scope_type: str, scope_id: str, cohort_key: str, feature_name: str, window: str) -> BaselineRecord | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM ai_baselines
                    WHERE scope_type = %(scope_type)s AND scope_id = %(scope_id)s
                      AND cohort_key = %(cohort_key)s AND feature_name = %(feature_name)s AND window = %(window)s
                    LIMIT 1
                    """,
                    {"scope_type": scope_type, "scope_id": scope_id, "cohort_key": cohort_key, "feature_name": feature_name, "window": window},
                )
                row = cur.fetchone()
        if not row:
            return None
        return BaselineRecord(
            scope_type=row["scope_type"], scope_id=row["scope_id"], cohort_key=row["cohort_key"],
            feature_name=row["feature_name"], window=row["window"],
            p50=float(row["p50"]), p75=float(row["p75"]), p90=float(row["p90"]),
            n_samples=int(row["n_samples"]), computed_at=row["computed_at"],
        )


class ProposalStorePG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_latest_ok(self, insight_id: str) -> StoredProposal | None:
        return self._get_latest(insight_id, status_filter="ok")

    def get_latest(self, insight_id: str) -> StoredProposal | None:
        return self._get_latest(insight_id, status_filter=None)

    def _get_latest(self, insight_id: str, status_filter: str | None) -> StoredProposal | None:
        where = "insight_id = %(insight_id)s"
        if status_filter:
            where += " AND status = %(status)s"
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM ai_insight_proposals WHERE {where} ORDER BY created_at DESC LIMIT 1",
                    {"insight_id": insight_id, "status": status_filter},
                )
                row = cur.fetchone()
        if not row:
            return None
        proposal = row.get("proposal") or {}
        if isinstance(proposal, str):
            proposal = json.loads(proposal)
        return StoredProposal(
            id=str(row["id"]),
            insight_id=str(row["insight_id"]),
            project_id=str(row["project_id"]),
            proposal=proposal,
            prompt_version=str(row.get("prompt_version", "")),
            tools_catalog_version=str(row.get("tools_catalog_version", "")),
            llm_provider=str(row.get("llm_provider", "")),
            llm_model=str(row.get("llm_model", "")),
            status=str(row.get("status", "")),
            error_message=str(row.get("error_message", "")),
            created_at=row.get("created_at"),
        )

    def insert(
        self,
        *,
        insight_id: str,
        project_id: str,
        proposal: dict[str, Any],
        prompt_version: str,
        tools_catalog_version: str,
        llm_provider: str,
        llm_model: str,
        status: str,
        error_message: str,
    ) -> str:
        pid = str(uuid.uuid4())
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_insight_proposals (
                        id, insight_id, project_id, proposal,
                        prompt_version, tools_catalog_version, llm_provider, llm_model,
                        status, error_message, created_at
                    ) VALUES (
                        %(id)s, %(insight_id)s, %(project_id)s, %(proposal)s::jsonb,
                        %(prompt_version)s, %(tools_catalog_version)s, %(llm_provider)s, %(llm_model)s,
                        %(status)s, %(error_message)s, NOW()
                    )
                    """,
                    {
                        "id": pid,
                        "insight_id": insight_id,
                        "project_id": project_id,
                        "proposal": json.dumps(proposal),
                        "prompt_version": prompt_version,
                        "tools_catalog_version": tools_catalog_version,
                        "llm_provider": llm_provider,
                        "llm_model": llm_model,
                        "status": status,
                        "error_message": error_message,
                    },
                )
            conn.commit()
        return pid


class InsightHistoryPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_history(self, project_id: str, entity_type: str, entity_id: str, limit: int = 10) -> list[InsightHistoryItem]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, type, severity, status, computed_at, title
                    FROM ai_insights
                    WHERE project_id = %(project_id)s AND entity_type = %(entity_type)s AND entity_id = %(entity_id)s
                    ORDER BY computed_at DESC LIMIT %(limit)s
                    """,
                    {"project_id": project_id, "entity_type": entity_type, "entity_id": entity_id, "limit": limit},
                )
                rows = cur.fetchall()
        return [
            InsightHistoryItem(id=str(r["id"]), type=r["type"], severity=r["severity"], status=r["status"], computed_at=r["computed_at"], title=r["title"])
            for r in rows
        ]

    def get_recent_actions(self, project_id: str, limit: int = 10) -> list[InsightActionItem]:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT insight_id, user_id, action, created_at
                    FROM ai_insight_actions
                    WHERE project_id = %(project_id)s
                    ORDER BY created_at DESC LIMIT %(limit)s
                    """,
                    {"project_id": project_id, "limit": limit},
                )
                rows = cur.fetchall()
        return [
            InsightActionItem(insight_id=str(r["insight_id"]), user_id=str(r["user_id"]), action=r["action"], created_at=r["created_at"])
            for r in rows
        ]
