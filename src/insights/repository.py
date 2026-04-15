"""Repositorio mínimo PG para insights legacy.

Solo expone `get_summary` (para alimentar el dossier del chat agent). Los
insights "vivos" ahora viven en ponti-backend (`business_insight_candidates`).
La tabla local `ai_insights` queda como compatibilidad: si está vacía, devuelve
counts en cero, lo cual es OK para el dossier.
"""

from __future__ import annotations

import psycopg
from runtime.logging import get_logger

from src.config import Settings
from src.db.session import DBSession
from src.insights.domain import InsightSummary, TopInsight

HANDLED_DB_ERRORS = (psycopg.Error, ValueError, OSError)
logger = get_logger(__name__)


class InsightRepositoryPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_summary(self, project_id: str) -> InsightSummary:
        try:
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
                        SELECT id, type, severity, status, computed_at, title
                        FROM ai_insights
                        WHERE project_id = %(pid)s AND status = 'new' AND valid_until >= NOW()
                        ORDER BY severity DESC, computed_at DESC LIMIT 20
                        """,
                        {"pid": project_id},
                    )
                    rows = cur.fetchall()
        except HANDLED_DB_ERRORS as exc:
            logger.warning("get_summary_failed", project_id=project_id, error=str(exc))
            return InsightSummary(new_count_total=0, new_count_high_severity=0, top_insights=[])
        top_insights = [
            TopInsight(id=str(r["id"]), title=r["title"], severity=int(r["severity"]), status=r["status"])
            for r in rows
        ]
        return InsightSummary(new_count_total=total, new_count_high_severity=high, top_insights=top_insights)
