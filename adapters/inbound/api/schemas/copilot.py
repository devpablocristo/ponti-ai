from typing import Any

from pydantic import BaseModel


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


class CopilotExplanation(BaseModel):
    human_readable: str
    audit_focused: str
    what_to_watch_next: str


class ExplainInsightResponse(BaseModel):
    insight_id: str
    mode: str
    explanation: CopilotExplanation
    proposal: dict[str, Any] | None = None
