from fastapi import FastAPI

from adapters.inbound.api.dependencies import AppContainer
from adapters.inbound.api.routes.chat import router as chat_router
from adapters.inbound.api.routes.copilot import router as copilot_router
from adapters.inbound.api.routes.health import router as health_router
from adapters.inbound.api.routes.insights import router as insights_router
from adapters.outbound.db.repos.audit_logger_pg import AuditLoggerPG
from adapters.outbound.db.repos.insight_history_pg import InsightHistoryPG
from adapters.outbound.db.repos.baseline_repo_pg import BaselineRepositoryPG
from adapters.outbound.db.repos.feature_repo_pg import FeatureRepositoryPG
from adapters.outbound.db.repos.insight_repo_pg import InsightRepositoryPG
from adapters.outbound.db.repos.proposal_store_pg import ProposalStorePG
from adapters.outbound.llm.chat_provider_factory import build_chat_llm_provider
from runtime.completions import build_llm_client
from adapters.outbound.llm.copilot_explainer import CopilotExplainerLLM
from adapters.outbound.llm.insight_planner import InsightPlannerLLM
from adapters.outbound.models.anomaly_runner import AnomalyRunner
from app.config import load_settings
from contexts.copilot.application.use_cases.explain_insight import ExplainInsight
from contexts.insights.application.use_cases.compute_insights import ComputeInsights
from contexts.insights.application.use_cases.get_insights import GetInsights
from contexts.insights.application.use_cases.get_summary import GetSummary
from contexts.insights.application.use_cases.record_action import RecordAction


def create_app() -> FastAPI:
    settings = load_settings()

    audit_logger = AuditLoggerPG(settings)

    feature_repo = FeatureRepositoryPG(settings)
    insight_repo = InsightRepositoryPG(settings)
    insight_history = InsightHistoryPG(settings)
    proposal_store = ProposalStorePG(settings)
    baseline_repo = BaselineRepositoryPG(settings)

    llm_client = build_llm_client(settings, logger_name="ponti-ai.llm")
    chat_llm = build_chat_llm_provider(settings)
    insight_planner = InsightPlannerLLM(llm_client)
    copilot_explainer = CopilotExplainerLLM(llm_client)

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
    compute_insights = ComputeInsights(
        feature_repo,
        model_runner,
        insight_repo,
        audit_logger,
        proposal_store,
        insight_planner,
        insight_history,
        domain=settings.domain,
        max_actions_allowed=settings.max_actions_allowed,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model,
        copilot_enabled=settings.copilot_enabled,
    )
    explain_insight = ExplainInsight(
        insight_repo=insight_repo,
        proposal_store=proposal_store,
        explainer=copilot_explainer,
    )
    get_insights = GetInsights(insight_repo)
    get_summary = GetSummary(insight_repo)
    record_action = RecordAction(insight_repo, audit_logger)

    container = AppContainer(
        settings=settings,
        explain_insight=explain_insight,
        compute_insights=compute_insights,
        get_insights=get_insights,
        get_summary=get_summary,
        record_action=record_action,
        chat_llm=chat_llm,
    )

    app = FastAPI(title="Ponti AI", version="1.0.0-mvp")
    app.state.container = container
    app.include_router(health_router)
    app.include_router(insights_router)
    if settings.chat_enabled:
        app.include_router(chat_router)
    if settings.copilot_enabled:
        app.include_router(copilot_router)
    return app
