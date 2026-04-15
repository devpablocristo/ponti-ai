"""Factory de proveedor LLM para chat multi-turn (protocolo `LLMProvider.chat`)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from runtime.config.llm import normalize_provider
from runtime.domain.models import ChatChunk, LLMProvider, Message, ToolDeclaration

if TYPE_CHECKING:
    from src.config import Settings


class PontiStubChatProvider:
    """LLM de desarrollo: respuesta fija en español sin llamadas a red."""

    async def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolDeclaration] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        del tools, temperature, max_tokens
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        snippet = (last_user or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        text = (
            "Modo stub (sin modelo generativo). Recibí tu mensaje"
            + (f": «{snippet}»" if snippet else "")
            + ". Configurá LLM_PROVIDER=vertex|gemini|ollama y credenciales para respuestas reales."
        )
        yield ChatChunk(type="text", text=text)


def build_chat_llm_provider(settings: Any) -> LLMProvider:
    """Construye el proveedor de chat según `LLM_PROVIDER` (independiente del cliente JSON del copilot)."""
    provider = normalize_provider(getattr(settings, "llm_provider", "stub"))

    if provider == "stub":
        return PontiStubChatProvider()

    if provider in {"google", "google_ai_studio", "gemini"}:
        from runtime.providers.gemini import GeminiProvider

        api_key = str(getattr(settings, "llm_api_key", "") or "").strip()
        if not api_key:
            return PontiStubChatProvider()
        model = str(getattr(settings, "llm_model", "") or "").strip() or "gemini-2.0-flash"
        return GeminiProvider(api_key=api_key, model=model)

    if provider in {"vertex", "vertex_ai"}:
        from runtime.providers.gemini import GeminiProvider

        project = str(getattr(settings, "llm_project", "") or "").strip()
        if not project:
            return PontiStubChatProvider()
        location = str(getattr(settings, "llm_location", "") or "").strip() or "us-central1"
        model = str(getattr(settings, "llm_model", "") or "").strip() or "gemini-2.0-flash"
        return GeminiProvider(vertex_project=project, vertex_location=location, model=model)

    if provider == "ollama":
        from runtime.providers.ollama import OllamaProvider

        base_url = str(getattr(settings, "llm_base_url", "") or "http://localhost:11434").rstrip("/")
        model = str(getattr(settings, "llm_model", "") or "").strip() or "llama3.1"
        timeout_ms = int(getattr(settings, "llm_timeout_ms", 5000) or 5000)
        return OllamaProvider(base_url=base_url, model=model, timeout=max(timeout_ms / 1000.0, 1.0))

    # openai u otros: solo JSON completion hoy — chat usa stub explícito
    return PontiStubChatProvider()
