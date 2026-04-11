"""Schemas de request/response para insights e insight_chat."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.runtime_contracts import OUTPUT_KIND_INSIGHT_CHAT_EXPLANATION, OUTPUT_KIND_INSIGHT_SUMMARY, SERVICE_KIND_INSIGHT


# --- Insights ---

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
    evidence: dict[str, Any] = Field(default_factory=dict)
    explanations: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    model_version: str = ""
    features_version: str = ""
    computed_at: str = ""
    valid_until: str = ""
    status: str = ""
    impact_min: float | None = None
    impact_max: float | None = None
    impact_unit: str | None = None
    confidence: str | None = None
    dedupe_key: str | None = None
    cooldown_until: str | None = None
    computed_by: str = "on_demand"
    rules_version: str = "v1"


class ComputeInsightsResponse(BaseModel):
    request_id: str
    service_kind: str = SERVICE_KIND_INSIGHT
    computed: int
    insights_created: int


class InsightListResponse(BaseModel):
    request_id: str
    service_kind: str = SERVICE_KIND_INSIGHT
    insights: list[InsightItem] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    request_id: str
    service_kind: str = SERVICE_KIND_INSIGHT
    output_kind: str = OUTPUT_KIND_INSIGHT_SUMMARY
    new_count_total: int
    new_count_high_severity: int
    top_insights: list[InsightItem] = Field(default_factory=list)


class ActionRequest(BaseModel):
    action: str
    new_status: str


class ActionResponse(BaseModel):
    request_id: str
    service_kind: str = SERVICE_KIND_INSIGHT
    status: str


# --- Copilot ---

class InsightChatExplanation(BaseModel):
    human_readable: str = ""
    audit_focused: str = ""
    what_to_watch_next: str = ""


class ExplainInsightResponse(BaseModel):
    request_id: str
    output_kind: str = OUTPUT_KIND_INSIGHT_CHAT_EXPLANATION
    routed_agent: str = "insight_chat"
    routing_source: str = "insight_chat_agent"
    insight_id: str
    mode: str
    explanation: InsightChatExplanation | dict[str, str] = Field(default_factory=dict)
    proposal: dict[str, Any] | None = None
