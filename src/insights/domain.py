"""Entidades y DTOs del dominio de insights."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Insight:
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
    computed_at: datetime
    valid_until: datetime
    status: str
    impact_min: float | None = None
    impact_max: float | None = None
    impact_unit: str | None = None
    confidence: str | None = None
    dedupe_key: str | None = None
    cooldown_until: datetime | None = None
    computed_by: str = "on_demand"
    job_run_id: str | None = None
    rules_version: str = "v1"


@dataclass(frozen=True)
class FeatureValue:
    project_id: str
    entity_type: str
    entity_id: str
    feature_name: str
    window: str
    value: float


@dataclass(frozen=True)
class InsightSummary:
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[dict[str, Any]]


@dataclass(frozen=True)
class BaselineRecord:
    scope_type: str
    scope_id: str
    cohort_key: str
    feature_name: str
    window: str
    p50: float
    p75: float
    p90: float
    n_samples: int
    computed_at: datetime


@dataclass(frozen=True)
class ComputeInsightsResult:
    request_id: str
    computed: int
    insights_created: int
    rules_insights_created: int
    projected_insights: list[Insight]


@dataclass(frozen=True)
class RecordActionResult:
    request_id: str


@dataclass(frozen=True)
class InsightHistoryItem:
    id: str
    type: str
    severity: int
    status: str
    computed_at: datetime
    title: str


@dataclass(frozen=True)
class InsightActionItem:
    insight_id: str
    user_id: str
    action: str
    created_at: datetime


@dataclass(frozen=True)
class AuditRecord:
    request_id: str
    user_id: str
    project_id: str
    question: str
    intent: str
    query_id: str
    params: dict[str, Any]
    duration_ms: int
    rows_count: int
    status: str
    error: str


@dataclass(frozen=True)
class StoredProposal:
    id: str
    insight_id: str
    project_id: str
    proposal: dict[str, Any]
    prompt_version: str
    tools_catalog_version: str
    llm_provider: str
    llm_model: str
    status: str
    error_message: str
    created_at: datetime | None
