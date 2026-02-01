from dotenv import load_dotenv
from fastapi import FastAPI

from adapters.inbound.api.dependencies import AppContainer
from adapters.inbound.api.routes.copilot import router as copilot_router
from adapters.inbound.api.routes.health import router as health_router
from adapters.inbound.api.routes.insights import router as insights_router
from adapters.inbound.api.routes.jobs import router as jobs_router
from adapters.outbound.db.repos.audit_logger_pg import AuditLoggerPG
from adapters.outbound.db.repos.insight_reader_pg import InsightReaderPG
from adapters.outbound.db.job_lock_pg import JobLockPG
from adapters.outbound.db.repos.baseline_repo_pg import BaselineRepositoryPG
from adapters.outbound.db.repos.feature_repo_pg import FeatureRepositoryPG
from adapters.outbound.db.repos.insight_repo_pg import InsightRepositoryPG
from adapters.outbound.db.repos.rag_repo_pg import RagRepositoryPG
from adapters.outbound.models.anomaly_runner import AnomalyRunner
from adapters.outbound.models.intent_classifier import IntentClassifier
from adapters.outbound.sql.baseline_computer_pg import BaselineComputerPG
from adapters.outbound.sql.project_repo_pg import ProjectRepositoryPG
from adapters.outbound.sql.catalog_adapter import SQLCatalogAdapter
from adapters.outbound.sql.executor import SQLExecutor
from app.config import load_settings
from application.copilot.use_cases.ask_copilot import AskCopilot
from application.copilot.use_cases.ingest_rag import IngestRag
from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.use_cases.get_insights import GetInsights
from application.insights.use_cases.get_summary import GetSummary
from application.insights.use_cases.record_action import RecordAction
from application.insights.use_cases.recompute_active import RecomputeActive
from application.insights.use_cases.recompute_baselines import RecomputeBaselines


def create_app() -> FastAPI:
    load_dotenv()
    settings = load_settings()

    intent_classifier = IntentClassifier()
    sql_catalog = SQLCatalogAdapter()
    sql_executor = SQLExecutor(settings)
    rag_repo = RagRepositoryPG(settings)
    audit_logger = AuditLoggerPG(settings)
    insight_reader = InsightReaderPG(settings)

    ask_copilot = AskCopilot(
        settings=settings,
        intent_classifier=intent_classifier,
        sql_catalog=sql_catalog,
        sql_executor=sql_executor,
        rag_repo=rag_repo,
        audit_logger=audit_logger,
        insight_reader=insight_reader,
    )
    ingest_rag = IngestRag(rag_repo)

    feature_repo = FeatureRepositoryPG(settings)
    insight_repo = InsightRepositoryPG(settings)

    baseline_repo = BaselineRepositoryPG(settings)
    baseline_computer = BaselineComputerPG(settings)
    project_repo = ProjectRepositoryPG(settings)
    job_lock = JobLockPG(settings)

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
    compute_insights = ComputeInsights(feature_repo, model_runner, insight_repo, audit_logger)
    get_insights = GetInsights(insight_repo)
    get_summary = GetSummary(insight_repo)
    record_action = RecordAction(insight_repo, audit_logger)

    recompute_active = RecomputeActive(compute_insights, insight_repo, job_lock)
    recompute_baselines = RecomputeBaselines(baseline_computer, baseline_repo, project_repo, job_lock)

    container = AppContainer(
        settings=settings,
        ask_copilot=ask_copilot,
        ingest_rag=ingest_rag,
        compute_insights=compute_insights,
        get_insights=get_insights,
        get_summary=get_summary,
        record_action=record_action,
        recompute_active=recompute_active,
        recompute_baselines=recompute_baselines,
    )

    app = FastAPI(title="AI Copilot Service", version="0.2.0")
    app.state.container = container
    app.include_router(health_router)
    app.include_router(copilot_router)
    app.include_router(insights_router)
    app.include_router(jobs_router)
    return app


app = create_app()
