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
    impact_min: float | None = None
    impact_max: float | None = None
    impact_unit: str | None = None
    confidence: str | None = None
    dedupe_key: str | None = None
    cooldown_until: str | None = None
    computed_by: str | None = None
    job_run_id: str | None = None
    rules_version: str | None = None


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


class HealthStatusResponse(BaseModel):
    status: str


class MetricsSnapshotResponse(BaseModel):
    counters: dict[str, float] = Field(default_factory=dict)
    timers: dict[str, dict[str, float]] = Field(default_factory=dict)
