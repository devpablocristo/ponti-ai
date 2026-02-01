from typing import Any

from pydantic import BaseModel, Field


class InsightItem(BaseModel):
    id: str
    project_id: str
    entity_type: str
    entity_id: str
    type: str
    severity: int
    priority: int
    title: str
    summary: str
    evidence: dict[str, Any]
    explanations: dict[str, Any]
    action: dict[str, Any]
    model_version: str
    features_version: str
    computed_at: str
    valid_until: str
    status: str


class ComputeInsightsResponse(BaseModel):
    request_id: str
    computed: int
    insights_created: int


class InsightListResponse(BaseModel):
    insights: list[InsightItem]


class SummaryResponse(BaseModel):
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[InsightItem]


class ActionRequest(BaseModel):
    action: str = Field(..., min_length=1)
    new_status: str = Field(..., min_length=1)


class ActionResponse(BaseModel):
    request_id: str
    status: str


class JobRecomputeRequest(BaseModel):
    batch_size: int | None = None


class JobRecomputeBaselinesRequest(BaseModel):
    batch_size: int | None = None


class JobRecomputeBaselinesResponse(BaseModel):
    status: str
    job_run_id: str
    cohort_saved: int
    project_saved: int
