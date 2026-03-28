from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core_ai.completions import (
    LLMBudgetExceededError,
    LLMCompletion,
    LLMError,
    LLMRateLimitError,
    OllamaChatClient,
    StubLLMClient,
)
from adapters.outbound.llm.copilot_explainer import CopilotExplainerLLM
from contexts.insights.domain.entities import Insight


class _FailingLLM:
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        _ = (system_prompt, user_prompt)
        raise LLMError("timeout")


class _ValidLLM:
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        _ = (system_prompt, user_prompt)
        return LLMCompletion(
            provider="stub",
            model="stub",
            content='{"human_readable":"ok","audit_focused":"audit","what_to_watch_next":"watch"}',
            raw=None,
        )


class _RateLimitedLLM:
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        _ = (system_prompt, user_prompt)
        raise LLMRateLimitError("llm_global_rate_limit_exceeded")


class _BudgetExceededLLM:
    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        _ = (system_prompt, user_prompt)
        raise LLMBudgetExceededError("llm_budget_calls_exceeded")


class _FailingOllama(OllamaChatClient):
    def __init__(self, settings: SimpleNamespace) -> None:
        super().__init__(settings)
        self.calls = 0

    def _complete_json_once(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        _ = (system_prompt, user_prompt)
        self.calls += 1
        raise LLMError("transport")


def _make_insight() -> Insight:
    now = datetime.now(timezone.utc)
    return Insight(
        id="ins-1",
        project_id="p-1",
        entity_type="project",
        entity_id="p-1",
        type="anomaly",
        severity=80,
        priority=80,
        title="Costo fuera de baseline",
        summary="El costo crecio de forma inusual.",
        evidence={"feature": "cost_total", "value": 100.0},
        explanations={"rule": "baseline_percentile"},
        action={"action_type": "review_inputs"},
        model_version="v1",
        features_version="f1",
        computed_at=now,
        valid_until=now + timedelta(days=1),
        status="new",
    )


def test_copilot_explainer_returns_llm_payload_when_valid() -> None:
    explainer = CopilotExplainerLLM(_ValidLLM())  # type: ignore[arg-type]
    out = explainer.explain(insight=_make_insight(), proposal=None, mode="explain")
    assert out["human_readable"] == "ok"
    assert out["audit_focused"] == "audit"
    assert out["what_to_watch_next"] == "watch"


def test_copilot_explainer_fallbacks_when_llm_fails() -> None:
    explainer = CopilotExplainerLLM(_FailingLLM())  # type: ignore[arg-type]
    out = explainer.explain(insight=_make_insight(), proposal=None, mode="why")
    assert "Motivo de negocio" in out["human_readable"]
    assert "baseline_percentile" in out["audit_focused"]


def test_copilot_explainer_next_steps_mode() -> None:
    explainer = CopilotExplainerLLM(_FailingLLM())  # type: ignore[arg-type]
    out = explainer.explain(insight=_make_insight(), proposal=None, mode="next_steps")
    assert "Siguientes pasos" in out["human_readable"]


def test_copilot_explainer_rate_limit_propagates() -> None:
    explainer = CopilotExplainerLLM(_RateLimitedLLM())  # type: ignore[arg-type]
    with pytest.raises(LLMRateLimitError):
        explainer.explain(insight=_make_insight(), proposal=None, mode="explain")


def test_copilot_explainer_budget_exceeded_propagates() -> None:
    explainer = CopilotExplainerLLM(_BudgetExceededLLM())  # type: ignore[arg-type]
    with pytest.raises(LLMBudgetExceededError):
        explainer.explain(insight=_make_insight(), proposal=None, mode="explain")


def test_ollama_complete_json_uses_single_attempt() -> None:
    settings = SimpleNamespace(
        llm_base_url="http://localhost:11434",
        llm_model="llama3.1",
        llm_max_retries=5,
        llm_timeout_ms=5000,
        llm_max_output_tokens=700,
        llm_max_calls_per_request=3,
        llm_budget_tokens_per_request=2500,
        llm_rate_limit_rps=2.0,
    )
    client = _FailingOllama(settings)
    with pytest.raises(LLMError):
        client.complete_json(system_prompt="s", user_prompt="u")
    assert client.calls == 1


def test_stub_llm_budget_enforcement() -> None:
    import time

    settings = SimpleNamespace(
        llm_provider="stub",
        llm_model="stub",
        llm_api_key=None,
        llm_base_url=None,
        llm_timeout_ms=5000,
        llm_max_retries=1,
        llm_max_output_tokens=700,
        llm_max_calls_per_request=1,
        llm_budget_tokens_per_request=50000,
        llm_rate_limit_rps=1000.0,
    )
    client = StubLLMClient(settings)
    # Primera llamada OK
    with client.request_scope():
        client.complete_json(system_prompt="s", user_prompt="u")
        time.sleep(0.002)  # superar min_interval del rate limiter
        # Segunda llamada dentro del mismo scope: budget agotado (calls_left = 0)
        with pytest.raises(LLMBudgetExceededError):
            client.complete_json(system_prompt="s", user_prompt="u")
