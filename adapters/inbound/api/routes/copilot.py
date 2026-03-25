from fastapi import APIRouter, Depends, HTTPException, status

from adapters.inbound.api.auth.headers import require_headers
from core_ai.contexts import AuthContext
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.copilot import ExplainInsightResponse
from adapters.outbound.llm.client import LLMBudgetExceededError, LLMRateLimitError

router = APIRouter()


@router.get("/v1/copilot/insights/{insight_id}/explain", response_model=ExplainInsightResponse)
def copilot_explain(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    try:
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="explain")
    except (LLMRateLimitError, LLMBudgetExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
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
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="why")
    except (LLMRateLimitError, LLMBudgetExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
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
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode="next_steps")
    except (LLMRateLimitError, LLMBudgetExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight no encontrado")
    return ExplainInsightResponse(
        insight_id=result["insight_id"],
        mode=result["mode"],
        explanation=result["explanation"],
        proposal=result.get("proposal"),
    )
