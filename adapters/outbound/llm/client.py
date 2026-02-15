import hashlib
import json
import threading
import time
import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from math import ceil
from typing import Any

import httpx
from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter

from adapters.outbound.observability.logging import get_logger
from app.config import Settings

HANDLED_LLM_TRANSPORT_ERRORS = (ValueError, TypeError, OSError)
HANDLED_LLM_CONTENT_ERRORS = (KeyError, IndexError, TypeError, AttributeError, ValueError)
HANDLED_HTTP_DETAIL_ERRORS = (ValueError, TypeError, KeyError)


class LLMError(RuntimeError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMBudgetExceededError(LLMError):
    pass


@dataclass(frozen=True)
class LLMCompletion:
    provider: str
    model: str
    content: str
    raw: dict[str, Any] | None = None


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger("ponti-ai.llm")
        self._rate_limiter = _GlobalRateLimiter(rps=float(self.settings.llm_rate_limit_rps))

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        raise NotImplementedError

    @contextmanager
    def request_scope(self):
        state = _RequestBudgetState(
            calls_left=int(self.settings.llm_max_calls_per_request),
            tokens_left=int(self.settings.llm_budget_tokens_per_request),
        )
        token = _REQUEST_BUDGET.set(state)
        try:
            yield
        finally:
            _REQUEST_BUDGET.reset(token)

    def _enforce_limits(self, *, system_prompt: str, user_prompt: str) -> None:
        self._rate_limiter.acquire()
        budget = _REQUEST_BUDGET.get()
        is_scoped = budget is not None
        if budget is None:
            budget = _RequestBudgetState(
                calls_left=int(self.settings.llm_max_calls_per_request),
                tokens_left=int(self.settings.llm_budget_tokens_per_request),
            )
        if budget.calls_left <= 0:
            raise LLMBudgetExceededError("llm_budget_calls_exceeded")
        estimated_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
        estimated_tokens += int(self.settings.llm_max_output_tokens)
        if budget.tokens_left < estimated_tokens:
            raise LLMBudgetExceededError("llm_budget_tokens_exceeded")
        budget.calls_left -= 1
        budget.tokens_left -= estimated_tokens
        if is_scoped:
            _REQUEST_BUDGET.set(budget)


class StubLLMClient(LLMClient):
    """
    Cliente determinístico para tests/local. No usa red.
    Devuelve JSON válido (string) en función de una "hint" en el prompt.
    """

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self._enforce_limits(system_prompt=system_prompt, user_prompt=user_prompt)
        _ = system_prompt
        # Heurística simple: si el prompt menciona "COPILOT_EXPLAIN", devuelve explicación;
        # caso contrario devuelve propuesta.
        if "COPILOT_EXPLAIN_V2" in user_prompt:
            payload = {
                "human_readable": "Explicación (stub) del insight y su propuesta.",
                "audit_focused": "Explicación técnica (stub).",
                "what_to_watch_next": "Qué observar (stub).",
            }
        else:
            payload = {
                "classification": {"severity": "high", "actionability": "act", "confidence": 0.85},
                "decision_summary": {
                    "recommended_outcome": "propose_actions",
                    "primary_reason": "Stub: insight supera baseline con evidencia suficiente.",
                },
                "proposed_plan": [
                    {
                        "step": 1,
                        "action": "Stub: solicitar desglose causal del costo.",
                        "tool": "request_cost_breakdown",
                        "tool_args": {"feature": "cost_total", "time_window": "all"},
                        "rationale": "Stub: atacar causa.",
                        "reversible": True,
                    }
                ],
                "risks_and_uncertainties": ["Stub: output generado sin LLM real."],
                "explanation": {
                    "human_readable": "Stub: qué pasó y qué se sugiere.",
                    "audit_focused": "Stub: reglas aplicadas.",
                    "what_to_watch_next": "Stub: métricas a observar.",
                },
            }
        return LLMCompletion(provider="stub", model="stub", content=json.dumps(payload), raw=None)


class OpenAIChatCompletionsClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY es requerido cuando LLM_PROVIDER != stub")
        self.base_url = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        attempt_limit = max(int(self.settings.llm_max_retries), 1)
        retrying = Retrying(
            stop=stop_after_attempt(attempt_limit),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            reraise=True,
        )
        for _attempt in retrying:
            with _attempt:
                return self._complete_json_once(system_prompt=system_prompt, user_prompt=user_prompt)
        raise LLMError("No se pudo obtener respuesta del LLM (retries agotados)")

    def _complete_json_once(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self._enforce_limits(system_prompt=system_prompt, user_prompt=user_prompt)
        timeout = httpx.Timeout(float(self.settings.llm_timeout_ms) / 1000.0)
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}

        # Redacted logging: no loguear prompt completo.
        digest = hashlib.sha256((system_prompt + "\n" + user_prompt).encode("utf-8")).hexdigest()[:12]
        self.logger.info(
            json.dumps(
                {
                    "event": "llm.request",
                    "provider": "openai",
                    "model": self.settings.llm_model,
                    "prompt_sha": digest,
                    "system_len": len(system_prompt),
                    "user_len": len(user_prompt),
                }
            )
        )

        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": int(self.settings.llm_max_output_tokens),
        }
        # Si el modelo soporta JSON mode, esto ayuda a forzar salida estructurada.
        body["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = _safe_http_error_detail(exc.response)
            raise LLMError(f"LLM HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM HTTP error: {exc}") from exc
        except HANDLED_LLM_TRANSPORT_ERRORS as exc:
            raise LLMError(f"LLM error: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except HANDLED_LLM_CONTENT_ERRORS as exc:
            raise LLMError("Respuesta LLM inválida: missing choices[0].message.content") from exc

        return LLMCompletion(provider="openai", model=self.settings.llm_model, content=content, raw=data)


class GoogleAIStudioGenerateContentClient(LLMClient):
    """
    Google AI Studio (Gemini API) via Generative Language API.

    API shape (HTTP):
    POST {base_url}/models/{model}:generateContent
    Headers: x-goog-api-key: <key>
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY es requerido cuando LLM_PROVIDER != stub")
        self.base_url = (settings.llm_base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        attempt_limit = max(int(self.settings.llm_max_retries), 1)
        retrying = Retrying(
            stop=stop_after_attempt(attempt_limit),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            reraise=True,
        )
        for _attempt in retrying:
            with _attempt:
                return self._complete_json_once(system_prompt=system_prompt, user_prompt=user_prompt)
        raise LLMError("No se pudo obtener respuesta del LLM (retries agotados)")

    def _complete_json_once(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self._enforce_limits(system_prompt=system_prompt, user_prompt=user_prompt)
        timeout = httpx.Timeout(float(self.settings.llm_timeout_ms) / 1000.0)
        headers = {"x-goog-api-key": self.settings.llm_api_key}

        digest = hashlib.sha256((system_prompt + "\n" + user_prompt).encode("utf-8")).hexdigest()[:12]
        self.logger.info(
            json.dumps(
                {
                    "event": "llm.request",
                    "provider": "google_ai_studio",
                    "model": self.settings.llm_model,
                    "prompt_sha": digest,
                    "system_len": len(system_prompt),
                    "user_len": len(user_prompt),
                }
            )
        )

        model = self.settings.llm_model.strip()
        if model.startswith("models/"):
            model_path = model
        else:
            model_path = f"models/{model}"

        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": int(self.settings.llm_max_output_tokens),
            },
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(f"{self.base_url}/{model_path}:generateContent", headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = _safe_http_error_detail(exc.response)
            raise LLMError(f"LLM HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM HTTP error: {exc}") from exc
        except HANDLED_LLM_TRANSPORT_ERRORS as exc:
            raise LLMError(f"LLM error: {exc}") from exc

        try:
            candidates = data.get("candidates") or []
            if not candidates:
                raise LLMError("Respuesta LLM inválida: missing candidates[0]")
            parts = candidates[0]["content"].get("parts") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            content = "".join(texts).strip()
            if not content:
                raise LLMError("Respuesta LLM inválida: empty content")
        except KeyError as exc:
            raise LLMError("Respuesta LLM inválida: missing candidates[0].content.parts[*].text") from exc

        return LLMCompletion(provider="google_ai_studio", model=self.settings.llm_model, content=content, raw=data)


class OllamaChatClient(LLMClient):
    """
    Ollama (local) via HTTP API.

    POST {base_url}/api/chat
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.base_url = (settings.llm_base_url or "http://localhost:11434").rstrip("/")

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        # En local Ollama puede quedar sin respuesta cuando el modelo no esta listo.
        # Mantenemos una sola tentativa para no bloquear requests HTTP por minutos.
        attempt_limit = 1
        retrying = Retrying(
            stop=stop_after_attempt(attempt_limit),
            wait=wait_exponential_jitter(initial=0.5, max=4.0),
            reraise=True,
        )
        for _attempt in retrying:
            with _attempt:
                return self._complete_json_once(system_prompt=system_prompt, user_prompt=user_prompt)
        raise LLMError("No se pudo obtener respuesta del LLM (retries agotados)")

    def _complete_json_once(self, *, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self._enforce_limits(system_prompt=system_prompt, user_prompt=user_prompt)
        # Protege la latencia de endpoints copilot aun si el timeout global es alto.
        timeout = httpx.Timeout(min(float(self.settings.llm_timeout_ms) / 1000.0, 30.0))

        digest = hashlib.sha256((system_prompt + "\n" + user_prompt).encode("utf-8")).hexdigest()[:12]
        self.logger.info(
            json.dumps(
                {
                    "event": "llm.request",
                    "provider": "ollama",
                    "model": self.settings.llm_model,
                    "prompt_sha": digest,
                    "system_len": len(system_prompt),
                    "user_len": len(user_prompt),
                }
            )
        )

        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": int(self.settings.llm_max_output_tokens)},
            # Ollama moderno soporta format=json (fuerza JSON). Si el runtime lo ignora,
            # igual validamos el JSON al parsear aguas abajo.
            "format": "json",
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = _safe_http_error_detail(exc.response)
            raise LLMError(f"LLM HTTP {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM HTTP error: {exc}") from exc
        except HANDLED_LLM_TRANSPORT_ERRORS as exc:
            raise LLMError(f"LLM error: {exc}") from exc

        try:
            # /api/chat: { message: { content } }
            content = str((data.get("message") or {}).get("content") or "").strip()
            if not content:
                # /api/generate compatibility
                content = str(data.get("response") or "").strip()
            if not content:
                raise LLMError("Respuesta LLM inválida: empty content")
        except HANDLED_LLM_CONTENT_ERRORS as exc:
            raise LLMError("Respuesta LLM inválida: missing message.content/response") from exc

        return LLMCompletion(provider="ollama", model=self.settings.llm_model, content=content, raw=data)


def build_llm_client(settings: Settings) -> LLMClient:
    provider = (settings.llm_provider or "stub").strip().lower()
    if provider == "stub":
        return StubLLMClient(settings)
    if provider in {"openai"}:
        return OpenAIChatCompletionsClient(settings)
    if provider in {"google", "google_ai_studio", "gemini"}:
        return GoogleAIStudioGenerateContentClient(settings)
    if provider in {"ollama"}:
        return OllamaChatClient(settings)
    raise ValueError(f"LLM_PROVIDER no soportado: {settings.llm_provider}")


def _safe_http_error_detail(resp: httpx.Response) -> str:
    """
    Extrae un detalle corto de error HTTP sin loguear secrets.
    """
    try:
        payload = resp.json()
        # OpenAI: {"error": {"message": "..."}}
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            msg = payload["error"].get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:300]
        # Google: {"error": {"message": "..."}}
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            msg = payload["error"].get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:300]
    except HANDLED_HTTP_DETAIL_ERRORS:
        pass
    # Fallback: texto truncado.
    try:
        return (resp.text or "").strip()[:300] or "unknown_error"
    except HANDLED_LLM_TRANSPORT_ERRORS:
        return "unknown_error"


@dataclass
class _RequestBudgetState:
    calls_left: int
    tokens_left: int


class _GlobalRateLimiter:
    def __init__(self, rps: float) -> None:
        self.rps = max(0.1, float(rps))
        self._lock = threading.Lock()
        self._last_call_monotonic = 0.0

    def acquire(self) -> None:
        min_interval = 1.0 / self.rps
        now = time.monotonic()
        with self._lock:
            if now - self._last_call_monotonic < min_interval:
                raise LLMRateLimitError("llm_global_rate_limit_exceeded")
            self._last_call_monotonic = now


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, ceil(len(text) / 4))


_REQUEST_BUDGET: contextvars.ContextVar[_RequestBudgetState | None] = contextvars.ContextVar(
    "llm_request_budget",
    default=None,
)
