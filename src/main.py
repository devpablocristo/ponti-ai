"""Punto de entrada de la aplicación Ponti AI (nueva estructura src/)."""

from fastapi import FastAPI

from runtime.completions import build_llm_client

from src.agents.chat_provider_factory import build_chat_llm_provider
from src.api.insight_chat_router import router as insight_chat_router
from src.api.deps import AppContainer
from src.api.health import router as health_router
from src.api.insights_router import router as insights_router
from src.api.router import router as chat_router
from src.config import load_settings
from src.insight_chat.explainer import InsightChatExplainerLLM
from src.insight_chat.service import ExplainInsight
from src.insight_chat.insight_planner import InsightPlannerLLM
from src.insights.anomaly_runner import AnomalyRunner
from src.insights.repository import (
    AuditLoggerPG,
    BaselineRepositoryPG,
    FeatureRepositoryPG,
    InsightHistoryPG,
    InsightRepositoryPG,
    ProposalStorePG,
)
from src.insights.service import ComputeInsights, GetInsights, GetSummary, RecordAction


def create_app() -> FastAPI:
    settings = load_settings()

    # --- Repos ---
    audit_logger = AuditLoggerPG(settings)
    feature_repo = FeatureRepositoryPG(settings)
    insight_repo = InsightRepositoryPG(settings)
    insight_history = InsightHistoryPG(settings)
    proposal_store = ProposalStorePG(settings)
    baseline_repo = BaselineRepositoryPG(settings)

    # --- LLM ---
    llm_client = build_llm_client(settings, logger_name="ponti-ai.llm")
    chat_llm = build_chat_llm_provider(settings)
    insight_planner = InsightPlannerLLM(llm_client)
    insight_chat_explainer = InsightChatExplainerLLM(llm_client)

    # --- Model runner ---
    model_runner = AnomalyRunner(
        baseline_repo=baseline_repo,
        ratio_high=settings.insights_ratio_high,
        ratio_medium=settings.insights_ratio_medium,
        spike_ratio=settings.insights_spike_ratio,
        size_small_max=settings.insights_size_small_max,
        size_medium_max=settings.insights_size_medium_max,
        cooldown_days=settings.insights_cooldown_days,
        impact_k=settings.insights_impact_k,
        impact_cap=settings.insights_impact_cap,
    )

    # --- Use cases ---
    compute_insights = ComputeInsights(
        feature_repo, model_runner, insight_repo, audit_logger,
        proposal_store, insight_planner, insight_history,
        domain=settings.domain,
        max_actions_allowed=settings.max_actions_allowed,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        insight_chat_enabled=settings.insight_chat_enabled,
    )
    explain_insight = ExplainInsight(
        insight_repo=insight_repo,
        proposal_store=proposal_store,
        explainer=insight_chat_explainer,
    )
    get_insights = GetInsights(insight_repo)
    get_summary = GetSummary(insight_repo)
    record_action = RecordAction(insight_repo, audit_logger)

    # --- Container ---
    container = AppContainer(
        settings=settings,
        explain_insight=explain_insight,
        compute_insights=compute_insights,
        get_insights=get_insights,
        get_summary=get_summary,
        record_action=record_action,
        chat_llm=chat_llm,
    )

    # --- App ---
    app = FastAPI(title="Ponti AI", version="2.0.0")
    app.state.settings = settings
    app.state.container = container

    app.include_router(health_router)
    app.include_router(insights_router)
    if settings.insight_chat_enabled:
        app.include_router(insight_chat_router)
    if settings.chat_enabled:
        app.include_router(chat_router)

    return app
