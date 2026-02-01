import time

from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
    ActionRequest,
    ActionResponse,
    ComputeInsightsResponse,
    InsightItem,
    InsightListResponse,
    SummaryResponse,
)
from adapters.outbound.observability.logging import log_event
from adapters.outbound.observability.metrics import inc_counter, observe_ms

router = APIRouter()


@router.post("/v1/insights/compute", response_model=ComputeInsightsResponse)
def compute_insights(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ComputeInsightsResponse:
    started = time.time()
    result = container.compute_insights.handle(project_id=auth.project_id, user_id=auth.user_id)
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.compute.duration_ms", duration_ms)
    inc_counter("insights.compute.count", 1)
    log_event(
        "insights.compute",
        {
            "request_id": result["request_id"],
            "project_id": auth.project_id,
            "computed": result["computed"],
            "created": result["insights_created"],
            "status": "ok",
        },
    )
    return ComputeInsightsResponse(
        request_id=result["request_id"],
        computed=result["computed"],
        insights_created=result["insights_created"],
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
        project_id=auth.project_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    items = [
        InsightItem(
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
        )
        for insight in insights
    ]
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.get.duration_ms", duration_ms)
    inc_counter("insights.get.count", 1)
    log_event(
        "insights.get",
        {
            "project_id": auth.project_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "count": len(items),
            "status": "ok",
        },
    )
    return InsightListResponse(insights=items)


@router.get("/v1/insights/summary", response_model=SummaryResponse)
def get_summary(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> SummaryResponse:
    started = time.time()
    summary = container.get_summary.handle(project_id=auth.project_id)
    top_items = [
        InsightItem(
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
        )
        for insight in summary.top_insights
    ]
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.summary.duration_ms", duration_ms)
    inc_counter("insights.summary.count", 1)
    log_event(
        "insights.summary",
        {
            "project_id": auth.project_id,
            "new_total": summary.new_count_total,
            "new_high": summary.new_count_high_severity,
            "status": "ok",
        },
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
    result = container.record_action.handle(
        insight_id=insight_id,
        project_id=auth.project_id,
        user_id=auth.user_id,
        action=req.action,
        new_status=req.new_status,
    )
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("insights.action.duration_ms", duration_ms)
    inc_counter("insights.action.count", 1)
    log_event(
        "insights.action",
        {
            "request_id": result["request_id"],
            "project_id": auth.project_id,
            "insight_id": insight_id,
            "status": "ok",
        },
    )
    return ActionResponse(request_id=result["request_id"], status="ok")
