from typing import Any, Literal

from pydantic import BaseModel, Field
from app.runtime_contracts import OUTPUT_KIND_INSIGHT_SUMMARY, SERVICE_KIND_INSIGHT


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
    service_kind: Literal["insight_service"] = SERVICE_KIND_INSIGHT
    computed: int
    insights_created: int


class InsightListResponse(BaseModel):
    request_id: str
    service_kind: Literal["insight_service"] = SERVICE_KIND_INSIGHT
    insights: list[InsightItem]


class SummaryResponse(BaseModel):
    request_id: str
    service_kind: Literal["insight_service"] = SERVICE_KIND_INSIGHT
    output_kind: Literal["insight_summary"] = OUTPUT_KIND_INSIGHT_SUMMARY
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[InsightItem]


class ActionRequest(BaseModel):
    action: str = Field(..., min_length=1)
    new_status: str = Field(..., min_length=1)


class ActionResponse(BaseModel):
    request_id: str
    service_kind: Literal["insight_service"] = SERVICE_KIND_INSIGHT
    status: str


class HealthStatusResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    service: str
    version: str
    git_sha: str = ""
    build_time: str = ""
    api_version: str = "v1"


class MetricsSnapshotResponse(BaseModel):
    counters: dict[str, float] = Field(default_factory=dict)
    timers: dict[str, dict[str, float]] = Field(default_factory=dict)
