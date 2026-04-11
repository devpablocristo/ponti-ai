"""Dependencias FastAPI y container de la app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, Request, status

from src.config import Settings
from src.insight_chat.service import ExplainInsight
from src.insights.service import ComputeInsights, GetInsights, GetSummary, RecordAction


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    explain_insight: ExplainInsight
    compute_insights: ComputeInsights
    get_insights: GetInsights
    get_summary: GetSummary
    record_action: RecordAction
    chat_llm: Any


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    actor: str


def _allowed_service_keys(settings: Settings) -> set[str]:
    return {
        item.strip()
        for item in str(settings.ai_service_keys or "").split(",")
        if item.strip()
    }


def require_headers(
    request: Request,
    x_user_id: str = Header(..., alias="X-USER-ID"),
    x_project_id: str = Header(..., alias="X-PROJECT-ID"),
    x_service_key: str = Header(..., alias="X-SERVICE-KEY"),
) -> AuthContext:
    if not x_user_id.strip() or not x_project_id.strip() or not x_service_key.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing required headers")
    settings = get_container(request).settings
    if x_service_key.strip() not in _allowed_service_keys(settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid service key")
    return AuthContext(tenant_id=x_project_id.strip(), actor=x_user_id.strip())
