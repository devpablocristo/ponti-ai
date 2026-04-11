"""Esquemas HTTP del asistente de chat Ponti."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from runtime import OUTPUT_KIND_CHAT_REPLY

PontiRouteHint = Literal[
    "general",
    "insight_chat",
    "dashboard",
    "labors",
    "supplies",
    "campaigns",
    "lots",
    "stock",
    "reports",
]

RoutedAgent = Literal[
    "general",
    "insight_chat",
    "dashboard",
    "labors",
    "supplies",
    "campaigns",
    "lots",
    "stock",
    "reports",
]

RoutingSource = Literal["insight_chat_agent", "orchestrator", "read_fallback", "ui_hint"]


class ChatHandoff(BaseModel):
    """Contexto estructurado de handoff desde notificaciones o vistas de insight."""

    source: Literal["in_app_notification", "direct"] = Field(
        ...,
        description="Origen del handoff.",
    )
    notification_id: str | None = Field(
        default=None,
        min_length=1,
        description="ID de la notificación origen.",
    )
    insight_id: str | None = Field(
        default=None,
        min_length=1,
        description="ID del insight al que se ancla el turno.",
    )
    insight_scope: str | None = Field(
        default=None,
        description="Scope del insight (entity_type:entity_id o similar).",
    )
    period: str | None = Field(
        default=None,
        description="Período del insight.",
    )


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    chat_id: str | None = Field(default=None, max_length=40)
    handoff: ChatHandoff | None = Field(
        default=None,
        description="Contexto estructurado de handoff desde notificaciones.",
    )
    route_hint: PontiRouteHint | None = Field(
        default=None,
        description="Hint opcional para forzar el carril del turno actual.",
    )
    preferred_language: Literal["es", "en"] | None = None
    confirmed_actions: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    request_id: str
    output_kind: Literal["chat_reply"] = OUTPUT_KIND_CHAT_REPLY
    content_language: Literal["es", "en"]
    chat_id: str
    reply: str
    tokens_used: int
    tool_calls: list[str] = Field(default_factory=list)
    pending_confirmations: list[str] = Field(default_factory=list)
    blocks: list[dict[str, Any]] = Field(default_factory=list)
    routed_agent: RoutedAgent
    routing_source: RoutingSource


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationMessage(BaseModel):
    role: str
    content: str
    ts: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    routed_agent: RoutedAgent | None = None
    routing_source: RoutingSource | None = None


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[ConversationMessage]
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
