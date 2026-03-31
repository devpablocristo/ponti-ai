from fastapi import APIRouter, Depends, HTTPException, status
from uuid import uuid4

from adapters.inbound.api.auth.headers import require_headers
from app.runtime_contracts import OUTPUT_KIND_COPILOT_EXPLANATION, ROUTING_SOURCE_COPILOT_AGENT
from runtime.completions import LLMBudgetExceededError, LLMRateLimitError
from runtime.contexts import AuthContext
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.copilot import ExplainInsightResponse
from contexts.copilot.application.use_cases.explain_insight import InsightNotFoundError

router = APIRouter()


def _new_request_id() -> str:
    return str(uuid4())


@router.get("/v1/copilot/insights/{insight_id}/explain", response_model=ExplainInsightResponse)
def copilot_explain(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    request_id = _new_request_id()
    try:
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="explain")
    except LLMRateLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_rate_limited")
    except LLMBudgetExceededError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_budget_exceeded")
    except InsightNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        request_id=request_id,
        output_kind=OUTPUT_KIND_COPILOT_EXPLANATION,
        routed_agent="copilot",
        routing_source=ROUTING_SOURCE_COPILOT_AGENT,
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
    request_id = _new_request_id()
    try:
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="why")
    except LLMRateLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_rate_limited")
    except LLMBudgetExceededError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_budget_exceeded")
    except InsightNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        request_id=request_id,
        output_kind=OUTPUT_KIND_COPILOT_EXPLANATION,
        routed_agent="copilot",
        routing_source=ROUTING_SOURCE_COPILOT_AGENT,
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
    request_id = _new_request_id()
    try:
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="next-steps")
    except LLMRateLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_rate_limited")
    except LLMBudgetExceededError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="copilot_budget_exceeded")
    except InsightNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        request_id=request_id,
        output_kind=OUTPUT_KIND_COPILOT_EXPLANATION,
        routed_agent="copilot",
        routing_source=ROUTING_SOURCE_COPILOT_AGENT,
        insight_id=result["insight_id"],
        mode=result["mode"],
        explanation=result["explanation"],
        proposal=result.get("proposal"),
    )
