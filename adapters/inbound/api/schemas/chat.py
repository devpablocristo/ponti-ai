"""Esquemas HTTP del asistente de chat Ponti (compatibles con el contrato tipo Pymes/Ponti)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from runtime import OUTPUT_KIND_CHAT_REPLY

PontiRouteHint = Literal[
    "general",
    "dashboard",
    "labors",
    "supplies",
    "campaigns",
    "lots",
    "stock",
    "reports",
    "copilot",
]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    chat_id: str | None = Field(default=None, max_length=40)
    route_hint: PontiRouteHint | None = None
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
    routed_agent: PontiRouteHint | Literal["general"]
    routing_source: str


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


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[ConversationMessage]
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "ConversationDetail",
    "ConversationListResponse",
    "ConversationMessage",
    "ConversationSummary",
    "PontiRouteHint",
]
