"""Persistencia del dossier operativo por proyecto."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from psycopg.types.json import Json

from adapters.outbound.db.session import DBSession
from app.config import Settings


DEFAULT_PROJECT_DOSSIER: dict[str, Any] = {
    "project": {
        "id": "",
        "name": "",
        "customer_name": "",
        "campaign_name": "",
        "domain": "agriculture",
        "description": "",
        "fields": [],
        "managers": [],
        "investors": [],
        "surface_hectares": None,
        "last_backend_refresh_at": "",
        "last_dashboard_refresh_at": "",
    },
    "workspace": {
        "current_filters": {},
    },
    "learned_context": [],
    "memory": {
        "business_facts": [],
        "stable_business_facts": [],
        "open_loops": [],
        "decisions": [],
        "recent_threads": [],
        "user_profiles": {},
    },
    "insights_snapshot": {
        "new_count_total": 0,
        "new_count_high_severity": 0,
        "top_titles": [],
        "last_refreshed_at": "",
    },
    "dashboard_snapshot": {
        "operating_result_usd": "",
        "operating_margin_pct": "",
        "executed_usd": "",
        "budget_usd": "",
        "stock_usd": "",
        "total_hectares": "",
        "top_operational_items": [],
        "last_refreshed_at": "",
    },
}


@dataclass
class ProjectDossierRow:
    project_id: str
    dossier: dict[str, Any]
    version: int
    created_at: datetime | None
    updated_at: datetime | None


def _deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(target)
    for key, value in patch.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class ProjectDossierRepositoryPG:
    def __init__(self, settings: Settings) -> None:
        self.session = DBSession(settings)

    def get_or_create(self, project_id: str) -> ProjectDossierRow:
        row = self.get(project_id)
        if row is not None:
            return row
        now = datetime.now(UTC)
        dossier = copy.deepcopy(DEFAULT_PROJECT_DOSSIER)
        dossier["project"]["id"] = str(project_id)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_project_dossiers (project_id, dossier, version, created_at, updated_at)
                    VALUES (%(project_id)s, %(dossier)s::jsonb, 1, %(now)s, %(now)s)
                    ON CONFLICT (project_id) DO NOTHING
                    """,
                    {"project_id": project_id, "dossier": Json(dossier), "now": now},
                )
                conn.commit()
        return self.get(project_id) or ProjectDossierRow(
            project_id=str(project_id),
            dossier=dossier,
            version=1,
            created_at=now,
            updated_at=now,
        )

    def get(self, project_id: str) -> ProjectDossierRow | None:
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT project_id, dossier, version, created_at, updated_at
                    FROM ai_project_dossiers
                    WHERE project_id = %(project_id)s
                    """,
                    {"project_id": project_id},
                )
                row = cur.fetchone()
        if row is None:
            return None
        dossier = row.get("dossier") or {}
        if not isinstance(dossier, dict):
            dossier = copy.deepcopy(DEFAULT_PROJECT_DOSSIER)
        dossier = _deep_merge(DEFAULT_PROJECT_DOSSIER, dossier)
        dossier["project"]["id"] = str(project_id)
        return ProjectDossierRow(
            project_id=str(row["project_id"]),
            dossier=dossier,
            version=int(row.get("version") or 1),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def save(self, project_id: str, dossier: dict[str, Any]) -> ProjectDossierRow:
        current = self.get_or_create(project_id)
        merged = _deep_merge(current.dossier, dossier)
        merged["project"]["id"] = str(project_id)
        now = datetime.now(UTC)
        with self.session.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ai_project_dossiers (project_id, dossier, version, created_at, updated_at)
                    VALUES (%(project_id)s, %(dossier)s::jsonb, 1, %(now)s, %(now)s)
                    ON CONFLICT (project_id) DO UPDATE SET
                        dossier = EXCLUDED.dossier,
                        version = ai_project_dossiers.version + 1,
                        updated_at = EXCLUDED.updated_at
                    """,
                    {"project_id": project_id, "dossier": Json(merged), "now": now},
                )
                conn.commit()
        return self.get_or_create(project_id)
