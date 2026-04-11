import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from runtime.completions import JSONCompletionClient as LLMClient, validate_json_completion
from src.insight_chat.prompts import INSIGHT_PLANNER_PROMPT_VERSION, INSIGHT_PLANNER_SYSTEM_PROMPT, INSIGHT_PLANNER_USER_PROMPT_TEMPLATE
from src.insight_chat.tools_catalog import TOOLS_CATALOG_VERSION, list_tools_as_json, validate_tool_args
from src.insights.domain import Insight


class _Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["low", "medium", "high"]
    actionability: Literal["none", "monitor", "act"]
    confidence: float = Field(..., ge=0.0, le=1.0)


class _DecisionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_outcome: Literal["no_action", "monitor", "propose_actions"]
    primary_reason: str = Field(..., min_length=1)


class _PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    tool: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(..., min_length=1)
    reversible: bool


class _Explanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    human_readable: str = Field(..., min_length=1)
    audit_focused: str = Field(..., min_length=1)
    what_to_watch_next: str = Field(..., min_length=1)


class _Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: _Classification
    decision_summary: _DecisionSummary
    proposed_plan: list[_PlanStep]
    risks_and_uncertainties: list[str]
    explanation: _Explanation


class InsightPlannerLLM:
    prompt_version: str = INSIGHT_PLANNER_PROMPT_VERSION
    tools_catalog_version: str = TOOLS_CATALOG_VERSION

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def request_scope(self):
        if hasattr(self.llm, "request_scope"):
            return self.llm.request_scope()
        raise RuntimeError("llm_request_scope_unavailable")

    def plan(
        self,
        *,
        insight: Insight,
        historical_context: dict[str, Any],
        domain: str,
        max_actions_allowed: int,
    ) -> dict[str, Any]:
        available_tools = list_tools_as_json()
        user_prompt = INSIGHT_PLANNER_USER_PROMPT_TEMPLATE.format(
            prompt_version=INSIGHT_PLANNER_PROMPT_VERSION,
            domain=domain,
            max_actions_allowed=max_actions_allowed,
            insight_json=json.dumps(_insight_to_prompt_dict(insight), ensure_ascii=True),
            historical_json=json.dumps(historical_context, ensure_ascii=True),
            tools_json=json.dumps(available_tools, ensure_ascii=True),
        )

        completion = self.llm.complete_json(system_prompt=INSIGHT_PLANNER_SYSTEM_PROMPT, user_prompt=user_prompt)

        try:
            proposal = validate_json_completion(completion.content, _Proposal)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM devolvió JSON inválido") from exc

        max_actions = max(int(max_actions_allowed), 0)
        trimmed_plan: list[_PlanStep] = [] if max_actions == 0 else proposal.proposed_plan[:max_actions]

        validated_plan: list[dict[str, Any]] = []
        for item in trimmed_plan:
            tool = item.tool
            tool_args = item.tool_args or {}
            if tool is not None:
                ok, err = validate_tool_args(tool, tool_args)
                if not ok:
                    raise ValueError(f"tool_args inválido para tool={tool}: {err}")
            validated_plan.append(
                {
                    "step": item.step,
                    "action": item.action,
                    "tool": tool,
                    "tool_args": tool_args,
                    "rationale": item.rationale,
                    "reversible": bool(item.reversible),
                }
            )

        output = proposal.model_dump()
        output["proposed_plan"] = validated_plan
        return output


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

