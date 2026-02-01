from typing import Any

from pydantic import BaseModel, Field


class AskContext(BaseModel):
    date_from: str | None = None
    date_to: str | None = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: AskContext | None = None


class AskResponse(BaseModel):
    request_id: str
    intent: str
    query_id: str | None
    params: dict[str, Any]
    data: list[dict[str, Any]]
    answer: str
    sources: list[dict[str, Any]]
    warnings: list[str]
    related_insights_count: int
    related_insights: list[dict[str, Any]]


class IngestDocument(BaseModel):
    source: str
    title: str
    content: str
    metadata: dict[str, Any] | None = None


class IngestRequest(BaseModel):
    documents: list[IngestDocument]


class IngestResponse(BaseModel):
    request_id: str
    ingested: int
