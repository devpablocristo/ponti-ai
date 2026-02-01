from dataclasses import dataclass

from fastapi import Request

from application.copilot.use_cases.ask_copilot import AskCopilot
from application.copilot.use_cases.ingest_rag import IngestRag
from application.insights.use_cases.compute_insights import ComputeInsights
from application.insights.use_cases.get_insights import GetInsights
from application.insights.use_cases.get_summary import GetSummary
from application.insights.use_cases.record_action import RecordAction
from application.insights.use_cases.recompute_active import RecomputeActive
from application.insights.use_cases.recompute_baselines import RecomputeBaselines
from app.config import Settings


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    ask_copilot: AskCopilot
    ingest_rag: IngestRag
    compute_insights: ComputeInsights
    get_insights: GetInsights
    get_summary: GetSummary
    record_action: RecordAction
    recompute_active: RecomputeActive
    recompute_baselines: RecomputeBaselines


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
