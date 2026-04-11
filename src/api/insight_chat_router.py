"""Rutas HTTP de insight_chat para explain/why/next-steps."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from runtime.completions import LLMBudgetExceededError, LLMRateLimitError

from src.api.deps import AppContainer, AuthContext, get_container, require_headers
from src.api.schemas import ExplainInsightResponse
from src.insight_chat.service import InsightNotFoundError
from src.runtime_contracts import OUTPUT_KIND_INSIGHT_CHAT_EXPLANATION, ROUTING_SOURCE_INSIGHT_CHAT_AGENT

router = APIRouter(prefix="/v1/insight-chat", tags=["insight_chat"])


def _handle_explain(insight_id: str, mode: str, auth: AuthContext, container: AppContainer) -> ExplainInsightResponse:
    try:
        result = container.explain_insight.handle(project_id=auth.tenant_id, insight_id=insight_id, mode=mode)
    except InsightNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="insight no encontrado")
    except LLMRateLimitError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limit del LLM alcanzado")
    except LLMBudgetExceededError:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="presupuesto de tokens agotado")

    return ExplainInsightResponse(
        request_id=str(uuid4()),
        output_kind=OUTPUT_KIND_INSIGHT_CHAT_EXPLANATION,
        routed_agent="insight_chat",
        routing_source=ROUTING_SOURCE_INSIGHT_CHAT_AGENT,
        insight_id=insight_id,
        mode=mode,
        explanation=result.get("explanation", {}),
        proposal=result.get("proposal"),
    )


@router.get("/insights/{insight_id}/explain", response_model=ExplainInsightResponse)
def insight_chat_explain(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    return _handle_explain(insight_id, "explain", auth, container)


@router.get("/insights/{insight_id}/why", response_model=ExplainInsightResponse)
def insight_chat_why(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    return _handle_explain(insight_id, "why", auth, container)


@router.get("/insights/{insight_id}/next-steps", response_model=ExplainInsightResponse)
def insight_chat_next_steps(
    insight_id: str,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> ExplainInsightResponse:
    return _handle_explain(insight_id, "next-steps", auth, container)
