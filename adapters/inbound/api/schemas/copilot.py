from pydantic import BaseModel

class CopilotExplanation(BaseModel):
    human_readable: str
    audit_focused: str
    what_to_watch_next: str


class ExplainInsightResponse(BaseModel):
    insight_id: str
    mode: str
    explanation: CopilotExplanation
    proposal: dict | None = None
