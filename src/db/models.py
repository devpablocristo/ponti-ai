"""Dataclasses para filas de las tablas ai_*."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ConversationRow:
    id: str
    project_id: str
    user_id: str
    mode: str
    title: str
    messages: list[dict[str, Any]]
    tool_calls_count: int
    tokens_input: int
    tokens_output: int
    created_at: datetime | None
    updated_at: datetime | None


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
        "last_route_hint": "",
        "recent_route_hints": [],
        "last_content_language": "",
    },
    "insight_chat_context": {
        "notification_id": "",
        "insight_id": "",
        "scope": "",
        "routed_agent": "",
        "content_language": "",
        "suggested_user_message": "",
        "source_kind": "",
        "last_handoff_at": "",
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


def deep_merge(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(target)
    for key, value in patch.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
