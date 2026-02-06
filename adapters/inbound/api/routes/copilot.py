import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.copilot import (
    ExplainInsightResponse,
    IngestRequest,
    IngestResponse,
)
from adapters.outbound.observability.logging import log_event
from adapters.outbound.observability.metrics import inc_counter, observe_ms

router = APIRouter()


@router.post("/v1/rag/ingest", response_model=IngestResponse)
def rag_ingest(
    req: IngestRequest,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> IngestResponse:
    started = time.time()
    request_id = str(uuid.uuid4())
    ingested = container.ingest_rag.handle(auth.project_id, req.documents)
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("rag.ingest.duration_ms", duration_ms)
    inc_counter("rag.ingest.count", 1)
    log_event(
        "rag.ingest",
        {
            "request_id": request_id,
            "project_id": auth.project_id,
            "ingested": ingested,
            "status": "ok",
        },
    )
    return IngestResponse(request_id=request_id, ingested=ingested)


@router.get("/v1/copilot/insights/{insight_id}/explain", response_model=ExplainInsightResponse)
def copilot_explain(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    try:
        result = container.explain_insight.handle(project_id=auth.project_id, insight_id=insight_id, mode="explain")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        insight_id=result["insight_id"],
        mode=result["mode"],
        explanation=result["explanation"],
        proposal=result.get("proposal"),
    )


@router.get("/v1/copilot/insights/{insight_id}/why", response_model=ExplainInsightResponse)
def copilot_why(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    try:
        result = container.explain_insight.handle(project_id=auth.project_id, insight_id=insight_id, mode="why")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        insight_id=result["insight_id"],
        mode=result["mode"],
        explanation=result["explanation"],
        proposal=result.get("proposal"),
    )


@router.get("/v1/copilot/insights/{insight_id}/next-steps", response_model=ExplainInsightResponse)
def copilot_next_steps(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    try:
        result = container.explain_insight.handle(project_id=auth.project_id, insight_id=insight_id, mode="next_steps")
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        insight_id=result["insight_id"],
        mode=result["mode"],
        explanation=result["explanation"],
        proposal=result.get("proposal"),
    )
