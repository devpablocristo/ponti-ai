from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from contexts.copilot.application.use_cases.explain_insight import ExplainInsight
from contexts.copilot.application.use_cases.ingest_rag import IngestRag
from contexts.insights.application.use_cases.compute_insights import ComputeInsights
from contexts.insights.application.use_cases.get_insights import GetInsights
from contexts.insights.application.use_cases.get_summary import GetSummary
from contexts.insights.application.use_cases.record_action import RecordAction
from contexts.insights.application.use_cases.recompute_active import RecomputeActive
from contexts.insights.application.use_cases.recompute_baselines import RecomputeBaselines
from contexts.insights.application.use_cases.queue_recompute_event import QueueRecomputeEvent
from contexts.insights.application.use_cases.process_recompute_queue import ProcessRecomputeQueue
from contexts.insights.application.ports.job_lock import JobLockPort
from app.config import Settings

# TYPE_CHECKING evita importar ml en runtime si no se usa
# Esto mantiene las dependencias ML opcionales
if TYPE_CHECKING:
    from contexts.ml import MLFacade


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    explain_insight: ExplainInsight
    ingest_rag: IngestRag
    compute_insights: ComputeInsights
    get_insights: GetInsights
    get_summary: GetSummary
    record_action: RecordAction
    recompute_active: RecomputeActive
    recompute_baselines: RecomputeBaselines
    queue_recompute_event: QueueRecomputeEvent
    process_recompute_queue: ProcessRecomputeQueue
    job_lock: JobLockPort
    # ML Facade (opcional, None si ML no esta habilitado)
    ml_facade: "MLFacade | None" = None


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
