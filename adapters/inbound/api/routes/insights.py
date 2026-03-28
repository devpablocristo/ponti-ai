import time

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.inbound.api.auth.headers import require_headers
from core_ai.logging import get_logger
from core_ai.contexts import AuthContext
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
    ActionRequest,
    ActionResponse,
    ComputeInsightsResponse,
    InsightItem,
    InsightListResponse,
    SummaryResponse,
)
from adapters.outbound.observability.metrics import inc_counter, observe_ms

router = APIRouter()
ALLOWED_ACTIONS = {"ack", "acknowledged", "snooze", "snoozed", "resolved"}
ALLOWED_NEW_STATUS = {"acknowledged", "snoozed", "resolved"}
logger = get_logger("ponti-ai.insights")


def _to_insight_item(insight) -> InsightItem:
    return InsightItem(
        id=insight.id,
        project_id=insight.project_id,
        entity_type=insight.entity_type,
        entity_id=insight.entity_id,
        type=insight.type,
        severity=insight.severity,
        priority=insight.priority,
        title=insight.title,
        summary=insight.summary,
        evidence=insight.evidence,
        explanations=insight.explanations,
        action=insight.action,
        model_version=insight.model_version,
        features_version=insight.features_version,
        computed_at=insight.computed_at.isoformat(),
        valid_until=insight.valid_until.isoformat(),
        status=insight.status,
        impact_min=insight.impact_min,
        impact_max=insight.impact_max,
        impact_unit=insight.impact_unit,
        confidence=insight.confidence,
        dedupe_key=insight.dedupe_key,
        cooldown_until=insight.cooldown_until.isoformat() if insight.cooldown_until else None,
        computed_by=insight.computed_by,
        job_run_id=insight.job_run_id,
        rules_version=insight.rules_version,
    )


@router.post("/v1/insights/compute", response_model=ComputeInsightsResponse)
def compute_insights(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ComputeInsightsResponse:
    started = time.time()
    try:
        result = container.compute_insights.handle(project_id=auth.tenant_id, user_id=auth.actor)
    except Exception as exc:
        duration_ms = int((time.time() - started) * 1000)
        observe_ms("insights.compute.duration_ms", duration_ms)
        inc_counter("insights.compute.error", 1)
        logger.info("insights.compute.error", project_id=auth.tenant_id, error=str(exc)[:200])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al computar insights")
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.compute.duration_ms", duration_ms)
    inc_counter("insights.compute.count", 1)
    inc_counter("insights.compute.rules_created", int(result.rules_insights_created))
    logger.info(
        "insights.compute",
        request_id=result.request_id,
        project_id=auth.tenant_id,
        computed=result.computed,
        created=result.insights_created,
        rules_created=int(result.rules_insights_created),
        status="ok",
    )
    return ComputeInsightsResponse(
        request_id=result.request_id,
        computed=result.computed,
        insights_created=result.insights_created,
    )


@router.get("/v1/insights/{entity_type}/{entity_id}", response_model=InsightListResponse)
def get_insights(
    entity_type: str,
    entity_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> InsightListResponse:
    started = time.time()
    insights = container.get_insights.handle(
        project_id=auth.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    items = [_to_insight_item(insight) for insight in insights]
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.get.duration_ms", duration_ms)
    inc_counter("insights.get.count", 1)
    logger.info(
        "insights.get",
        project_id=auth.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        count=len(items),
        status="ok",
    )
    return InsightListResponse(insights=items)


@router.get("/v1/insights/summary", response_model=SummaryResponse)
def get_summary(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> SummaryResponse:
    started = time.time()
    summary = container.get_summary.handle(project_id=auth.tenant_id)
    top_items = [_to_insight_item(insight) for insight in summary.top_insights]
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.summary.duration_ms", duration_ms)
    inc_counter("insights.summary.count", 1)
    logger.info(
        "insights.summary",
        project_id=auth.tenant_id,
        new_total=summary.new_count_total,
        new_high=summary.new_count_high_severity,
        status="ok",
    )
    return SummaryResponse(
        new_count_total=summary.new_count_total,
        new_count_high_severity=summary.new_count_high_severity,
        top_insights=top_items,
    )


@router.post("/v1/insights/{insight_id}/actions", response_model=ActionResponse)
def record_action(
    insight_id: str,
    req: ActionRequest,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ActionResponse:
    started = time.time()
    if req.action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action invalida")
    if req.new_status not in ALLOWED_NEW_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_status invalido")
    try:
        result = container.record_action.handle(
            insight_id=insight_id,
            project_id=auth.tenant_id,
            user_id=auth.actor,
            action=req.action,
            new_status=req.new_status,
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="insight_id invalido")
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.action.duration_ms", duration_ms)
    inc_counter("insights.action.count", 1)
    logger.info(
        "insights.action",
        request_id=result.request_id,
        project_id=auth.tenant_id,
        insight_id=insight_id,
        status="ok",
    )
    return ActionResponse(request_id=result.request_id, status="ok")
