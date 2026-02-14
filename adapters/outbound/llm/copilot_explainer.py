import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from adapters.outbound.llm.client import LLMBudgetExceededError, LLMClient, LLMError, LLMRateLimitError
from adapters.outbound.llm.prompts import (
    COPILOT_EXPLAIN_PROMPT_VERSION,
    COPILOT_EXPLAIN_SYSTEM_PROMPT,
    COPILOT_EXPLAIN_USER_PROMPT_TEMPLATE,
)
from contexts.copilot.application.ports.copilot_explainer import CopilotExplainerPort, CopilotExplainMode
from contexts.insights.domain.entities import Insight


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
        try:
            completion = self.llm.complete_json(system_prompt=COPILOT_EXPLAIN_SYSTEM_PROMPT, user_prompt=user_prompt)
            payload = json.loads(completion.content)
            out = _ExplainOut.model_validate(payload)
            return out.model_dump()
        except (LLMRateLimitError, LLMBudgetExceededError):
            raise
        except (LLMError, json.JSONDecodeError, ValueError):
            return _fallback_explanation(insight=insight, mode=mode)

    def request_scope(self):
        if hasattr(self.llm, "request_scope"):
            return self.llm.request_scope()
        raise RuntimeError("llm_request_scope_unavailable")


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


def _fallback_explanation(*, insight: Insight, mode: CopilotExplainMode) -> dict[str, str]:
    mode_text: dict[CopilotExplainMode, str] = {
        "explain": "Explicacion operativa del insight",
        "why": "Motivo de negocio y evidencia principal",
        "next_steps": "Siguientes pasos recomendados",
    }
    base = f"{mode_text[mode]}: {insight.title}. {insight.summary}"
    return {
        "human_readable": base,
        "audit_focused": f"Regla y evidencia: {insight.explanations} / {insight.evidence}",
        "what_to_watch_next": "Monitorear severidad, estado y recurrencia del mismo dedupe_key.",
    }
