from dotenv import load_dotenv
from fastapi import FastAPI

from adapters.inbound.api.dependencies import AppContainer
from adapters.inbound.api.routes.copilot import router as copilot_router
from adapters.inbound.api.routes.health import router as health_router
from adapters.inbound.api.routes.insights import router as insights_router
from adapters.inbound.api.routes.jobs import router as jobs_router
from adapters.inbound.api.routes.ml import router as ml_router
from adapters.outbound.db.repos.audit_logger_pg import AuditLoggerPG
from adapters.outbound.db.repos.insight_reader_pg import InsightReaderPG
from adapters.outbound.db.repos.insight_history_pg import InsightHistoryPG
from adapters.outbound.db.job_lock_pg import JobLockPG
from adapters.outbound.db.repos.baseline_repo_pg import BaselineRepositoryPG
from adapters.outbound.db.repos.feature_repo_pg import FeatureRepositoryPG
from adapters.outbound.db.repos.insight_repo_pg import InsightRepositoryPG
from adapters.outbound.db.repos.proposal_store_pg import ProposalStorePG
from adapters.outbound.db.repos.rag_repo_pg import RagRepositoryPG
from adapters.outbound.db.repos.recompute_queue_pg import RecomputeQueuePG
from adapters.outbound.llm.client import build_llm_client
from adapters.outbound.llm.copilot_explainer import CopilotExplainerLLM
from adapters.outbound.llm.insight_planner import InsightPlannerLLM
from adapters.outbound.models.anomaly_runner import AnomalyRunner
from adapters.outbound.sql.baseline_computer_pg import BaselineComputerPG
from adapters.outbound.sql.project_repo_pg import ProjectRepositoryPG
from app.config import load_settings
from application.copilot.use_cases.explain_insight import ExplainInsight
from application.copilot.use_cases.ingest_rag import IngestRag
from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.use_cases.get_insights import GetInsights
from application.insights.use_cases.get_summary import GetSummary
from application.insights.use_cases.record_action import RecordAction
from application.insights.use_cases.recompute_active import RecomputeActive
from application.insights.use_cases.recompute_baselines import RecomputeBaselines
from application.insights.use_cases.process_recompute_queue import ProcessRecomputeQueue
from application.insights.use_cases.queue_recompute_event import QueueRecomputeEvent


def _create_ml_facade(settings):
    """
    Crea el MLFacade si ML esta habilitado.

    Retorna None si ML no esta habilitado o hay error.
    Esto permite que la app funcione sin ML.
    """
    if not settings.ml_enabled:
        return None

    try:
        from ml import MLFacade
        return MLFacade.from_settings(settings)
    except Exception as e:
        # Log error pero no fallar - ML es opcional
        print(f"[WARN] No se pudo inicializar ML: {e}")
        return None


def create_app() -> FastAPI:
    load_dotenv()
    settings = load_settings()

    rag_repo = RagRepositoryPG(settings)
    audit_logger = AuditLoggerPG(settings)
    insight_reader = InsightReaderPG(settings)
    ingest_rag = IngestRag(rag_repo)

    feature_repo = FeatureRepositoryPG(settings)
    insight_repo = InsightRepositoryPG(settings)
    insight_history = InsightHistoryPG(settings)
    proposal_store = ProposalStorePG(settings)
    recompute_queue_repo = RecomputeQueuePG(settings)

    baseline_repo = BaselineRepositoryPG(settings)
    baseline_computer = BaselineComputerPG(settings)
    project_repo = ProjectRepositoryPG(settings)
    job_lock = JobLockPG(settings)

    llm_client = build_llm_client(settings)
    insight_planner = InsightPlannerLLM(llm_client)
    copilot_explainer = CopilotExplainerLLM(llm_client)
    ml_facade = _create_ml_facade(settings)

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
        ml_detector=ml_facade,
        ml_shadow_mode=settings.ml_shadow_mode,
    )
    explain_insight = ExplainInsight(
        insight_repo=insight_repo,
        proposal_store=proposal_store,
        explainer=copilot_explainer,
    )
    get_insights = GetInsights(insight_repo)
    get_summary = GetSummary(insight_repo)
    record_action = RecordAction(insight_repo, audit_logger)

    recompute_active = RecomputeActive(compute_insights, insight_repo, job_lock)
    recompute_baselines = RecomputeBaselines(baseline_computer, baseline_repo, project_repo, job_lock)
    queue_recompute_event = QueueRecomputeEvent(recompute_queue_repo)
    process_recompute_queue = ProcessRecomputeQueue(
        queue_repo=recompute_queue_repo,
        compute_insights=compute_insights,
        insight_repo=insight_repo,
        job_lock=job_lock,
    )

    container = AppContainer(
        settings=settings,
        explain_insight=explain_insight,
        ingest_rag=ingest_rag,
        compute_insights=compute_insights,
        get_insights=get_insights,
        get_summary=get_summary,
        record_action=record_action,
        recompute_active=recompute_active,
        recompute_baselines=recompute_baselines,
        queue_recompute_event=queue_recompute_event,
        process_recompute_queue=process_recompute_queue,
        job_lock=job_lock,
        ml_facade=ml_facade,
    )

    app = FastAPI(title="AI Copilot Service", version="0.3.0")
    app.state.container = container
    app.include_router(health_router)
    app.include_router(copilot_router)
    app.include_router(insights_router)
    app.include_router(jobs_router)
    app.include_router(ml_router)
    return app


app = create_app()
