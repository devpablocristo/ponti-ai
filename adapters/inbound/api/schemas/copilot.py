from typing import Literal

from pydantic import BaseModel
from app.runtime_contracts import OUTPUT_KIND_COPILOT_EXPLANATION, ROUTING_SOURCE_COPILOT_AGENT

class CopilotExplanation(BaseModel):
    human_readable: str
    audit_focused: str
    what_to_watch_next: str


class ExplainInsightResponse(BaseModel):
    request_id: str
    output_kind: Literal["copilot_explanation"] = OUTPUT_KIND_COPILOT_EXPLANATION
    routed_agent: Literal["copilot"] = "copilot"
    routing_source: Literal["copilot_agent"] = ROUTING_SOURCE_COPILOT_AGENT
    insight_id: str
    mode: Literal["explain", "why", "next-steps"]
    explanation: CopilotExplanation
    proposal: dict | None = None
