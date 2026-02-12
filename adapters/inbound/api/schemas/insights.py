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


class JobRecomputeRequest(BaseModel):
    batch_size: int | None = Field(default=None, ge=1, le=10000)


class JobRecomputeResponse(BaseModel):
    status: str
    job_run_id: str


class RecomputeEventRequest(BaseModel):
    source: str = Field(..., min_length=1)
    reason: str | None = None
    debounce_seconds: int | None = Field(default=None, ge=0, le=86400)


class RecomputeEventResponse(BaseModel):
    status: str
    project_id: str


class JobProcessQueueRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=1000)
    workers: int | None = Field(default=None, ge=1, le=64)


class JobProcessQueueResponse(BaseModel):
    status: str
    claimed: int
    processed: int
    ok: int
    locked: int
    errors: int


class JobRecomputeBaselinesRequest(BaseModel):
    batch_size: int | None = None


class JobRecomputeBaselinesResponse(BaseModel):
    status: str
    job_run_id: str
    cohort_saved: int
    project_saved: int


class JobRetrainMLRequest(BaseModel):
    version: str | None = None
    activate: bool = True
    auto_promote: bool = True
    hyperparameters: dict[str, Any] | None = None


class JobRetrainMLResponse(BaseModel):
    status: str
    job_run_id: str
    model_version: str | None = None
    active_version: str | None = None
    promoted: bool | None = None
    promotion_reason: str | None = None
    training_time_seconds: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class MLStatusResponse(BaseModel):
    enabled: bool
    initialized: bool
    model_type: str
    models_dir: str | None = None
    has_active_model: bool
    active_version: str | None = None
    available_versions: list[str] = Field(default_factory=list)
    rollout_percent: int = 100
    rollout_allowlist_size: int = 0
    last_drift_score: float | None = None
    last_drift_level: str | None = None
    shadow_mode: bool = False
    active_history: list[str] = Field(default_factory=list)
    auto_promote: bool = True
    auto_retrain_min_hours: int = 24


class MLActivateRequest(BaseModel):
    version: str = Field(..., min_length=1)


class MLRollbackRequest(BaseModel):
    target_version: str | None = None


class MLVersionChangeResponse(BaseModel):
    status: str
    previous_active_version: str | None = None
    active_version: str | None = None
    rollback_target_version: str | None = None
    error: str | None = None


class HealthStatusResponse(BaseModel):
    status: str


class MetricsSnapshotResponse(BaseModel):
    counters: dict[str, float] = Field(default_factory=dict)
    timers: dict[str, dict[str, float]] = Field(default_factory=dict)
