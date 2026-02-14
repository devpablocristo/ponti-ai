from dataclasses import dataclass

from fastapi import Request

from contexts.copilot.application.use_cases.explain_insight import ExplainInsight
from contexts.insights.application.use_cases.compute_insights import ComputeInsights
from contexts.insights.application.use_cases.get_insights import GetInsights
from contexts.insights.application.use_cases.get_summary import GetSummary
from contexts.insights.application.use_cases.record_action import RecordAction
from app.config import Settings


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    explain_insight: ExplainInsight
    compute_insights: ComputeInsights
    get_insights: GetInsights
    get_summary: GetSummary
    record_action: RecordAction


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
