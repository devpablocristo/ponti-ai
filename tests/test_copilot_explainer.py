from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from adapters.outbound.llm.client import LLMCompletion, LLMError, OllamaChatClient
from adapters.outbound.llm.copilot_explainer import CopilotExplainerLLM
from domain.insights.entities import Insight


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


def test_ollama_complete_json_uses_single_attempt() -> None:
    settings = SimpleNamespace(llm_base_url="http://localhost:11434", llm_model="llama3.1", llm_max_retries=5, llm_timeout_s=120.0)
    client = _FailingOllama(settings)
    with pytest.raises(LLMError):
        client.complete_json(system_prompt="s", user_prompt="u")
    assert client.calls == 1
