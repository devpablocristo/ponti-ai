"""Rutas HTTP de insights."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import AppContainer, AuthContext, get_container, require_headers
from src.api.schemas import (
    ActionRequest,
    ActionResponse,
    ComputeInsightsResponse,
    InsightItem,
    InsightListResponse,
    SummaryResponse,
)
from src.runtime_contracts import SERVICE_KIND_INSIGHT

router = APIRouter(prefix="/v1/insights", tags=["insights"])

ALLOWED_ACTIONS = {"acknowledge", "snooze", "resolve", "dismiss", "escalate", "ack"}
ALLOWED_NEW_STATUS = {"new", "acknowledged", "snoozed", "resolved", "dismissed", "escalated"}


def _to_insight_item(insight) -> InsightItem:
    return InsightItem(
        id=str(insight.id),
        project_id=str(insight.project_id),
        entity_type=insight.entity_type,
        entity_id=insight.entity_id,
        type=insight.type,
        severity=insight.severity,
        priority=insight.priority,
        title=insight.title,
        summary=insight.summary,
        evidence=insight.evidence if isinstance(insight.evidence, dict) else {},
        explanations=insight.explanations if isinstance(insight.explanations, dict) else {},
        action=insight.action if isinstance(insight.action, dict) else {},
        model_version=insight.model_version,
        features_version=insight.features_version,
        computed_at=insight.computed_at.isoformat() if insight.computed_at else "",
        valid_until=insight.valid_until.isoformat() if insight.valid_until else "",
        status=insight.status,
        impact_min=insight.impact_min,
        impact_max=insight.impact_max,
        impact_unit=insight.impact_unit,
        confidence=insight.confidence,
        dedupe_key=insight.dedupe_key,
        cooldown_until=insight.cooldown_until.isoformat() if insight.cooldown_until else None,
        computed_by=insight.computed_by,
        rules_version=insight.rules_version,
    )


@router.post("/compute", response_model=ComputeInsightsResponse)
def compute_insights(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ComputeInsightsResponse:
    result = container.compute_insights.handle(
        project_id=auth.tenant_id,
        user_id=auth.actor,
    )
    # Fase 8: no se hace push a notificaciones (unificación a vía pull/sync desde trigger)
    return ComputeInsightsResponse(
        request_id=result.request_id,
        service_kind=SERVICE_KIND_INSIGHT,
        computed=result.computed,
        insights_created=result.insights_created,
    )


@router.get("/{entity_type}/{entity_id}", response_model=InsightListResponse)
def get_insights(
    entity_type: str,
    entity_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> InsightListResponse:
    insights = container.get_insights.handle(auth.tenant_id, entity_type, entity_id)
    return InsightListResponse(
        request_id=str(uuid4()),
        service_kind=SERVICE_KIND_INSIGHT,
        insights=[_to_insight_item(i) for i in insights],
    )


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> SummaryResponse:
    summary = container.get_summary.handle(auth.tenant_id)
    return SummaryResponse(
        request_id=str(uuid4()),
        service_kind=SERVICE_KIND_INSIGHT,
        new_count_total=summary.new_count_total,
        new_count_high_severity=summary.new_count_high_severity,
        top_insights=[_to_insight_item(i) for i in summary.top_insights],
    )


@router.post("/{insight_id}/actions", response_model=ActionResponse)
def record_action(
    insight_id: str,
    req: ActionRequest,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ActionResponse:
    action = req.action.strip().lower()
    new_status = req.new_status.strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"action no permitida: {action}")
    if new_status not in ALLOWED_NEW_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"status no permitido: {new_status}")

    result = container.record_action.handle(
        insight_id=insight_id,
        project_id=auth.tenant_id,
        user_id=auth.actor,
        action=action,
        new_status=new_status,
    )
    return ActionResponse(
        request_id=result.request_id,
        service_kind=SERVICE_KIND_INSIGHT,
        status="ok",
    )
