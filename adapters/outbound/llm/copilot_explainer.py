import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from adapters.outbound.llm.client import LLMClient
from adapters.outbound.llm.prompts import (
    COPILOT_EXPLAIN_PROMPT_VERSION,
    COPILOT_EXPLAIN_SYSTEM_PROMPT,
    COPILOT_EXPLAIN_USER_PROMPT_TEMPLATE,
)
from application.copilot.ports.copilot_explainer import CopilotExplainerPort, CopilotExplainMode
from domain.insights.entities import Insight


class _ExplainOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_readable: str = Field(..., min_length=1)
    audit_focused: str = Field(..., min_length=1)
    what_to_watch_next: str = Field(..., min_length=1)


class CopilotExplainerLLM(CopilotExplainerPort):
    prompt_version: str = COPILOT_EXPLAIN_PROMPT_VERSION

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def explain(
        self,
        *,
        insight: Insight,
        proposal: dict[str, Any] | None,
        mode: CopilotExplainMode,
    ) -> dict[str, str]:
        user_prompt = COPILOT_EXPLAIN_USER_PROMPT_TEMPLATE.format(
            prompt_version=COPILOT_EXPLAIN_PROMPT_VERSION,
            mode=mode,
            insight_json=json.dumps(_insight_to_prompt_dict(insight), ensure_ascii=True),
            proposal_json=json.dumps(proposal or {}, ensure_ascii=True),
        )
        completion = self.llm.complete_json(system_prompt=COPILOT_EXPLAIN_SYSTEM_PROMPT, user_prompt=user_prompt)
        try:
            payload = json.loads(completion.content)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM devolvió JSON inválido (copilot)") from exc
        out = _ExplainOut.model_validate(payload)
        return out.model_dump()


def _insight_to_prompt_dict(insight: Insight) -> dict[str, Any]:
    return {
        "id": insight.id,
        "project_id": insight.project_id,
        "entity_type": insight.entity_type,
        "entity_id": insight.entity_id,
        "type": insight.type,
        "severity": insight.severity,
        "priority": insight.priority,
        "title": insight.title,
        "summary": insight.summary,
        "evidence": insight.evidence,
        "explanations": insight.explanations,
        "action": insight.action,
        "model_version": insight.model_version,
        "features_version": insight.features_version,
        "computed_at": insight.computed_at.isoformat(),
        "valid_until": insight.valid_until.isoformat(),
        "status": insight.status,
        "impact_min": insight.impact_min,
        "impact_max": insight.impact_max,
        "impact_unit": insight.impact_unit,
        "confidence": insight.confidence,
        "dedupe_key": insight.dedupe_key,
        "cooldown_until": insight.cooldown_until.isoformat() if insight.cooldown_until else None,
        "computed_by": insight.computed_by,
        "job_run_id": insight.job_run_id,
        "rules_version": insight.rules_version,
    }

