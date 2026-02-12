import os
import random

import httpx

from app.config import Settings


def embed_texts(settings: Settings, texts: list[str], dim: int) -> list[list[float]]:
    if not texts:
        return []

    provider, model = resolve_embedding_provider_model(settings)

    if provider == "stub":
        return _deterministic_embeddings(texts, dim)
    if provider == "openai":
        return _resize_embeddings(_embed_openai(settings, model, texts), dim)
    if provider in {"google", "google_ai_studio", "gemini"}:
        return _resize_embeddings(_embed_google(settings, model, texts), dim)
    if provider == "ollama":
        return _resize_embeddings(_embed_ollama(settings, model, texts), dim)

    raise RuntimeError(f"EMBEDDING_PROVIDER no soportado: {provider}")


def resolve_embedding_provider_model(settings: Settings) -> tuple[str, str]:
    provider = (os.getenv("EMBEDDING_PROVIDER") or settings.llm_provider or "stub").strip().lower()
    model = (os.getenv("EMBEDDING_MODEL") or _default_embedding_model(provider)).strip()
    return provider, model


def _embed_openai(settings: Settings, model: str, texts: list[str]) -> list[list[float]]:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY es requerido para embeddings OpenAI")
    base_url = (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/")
    timeout = httpx.Timeout(settings.llm_timeout_s)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
    rows = payload.get("data") or []
    vectors = [row.get("embedding") for row in rows if isinstance(row, dict)]
    if len(vectors) != len(texts):
        raise RuntimeError("OpenAI embeddings devolvio una cantidad invalida de vectores")
    return [[float(value) for value in vector] for vector in vectors]


def _embed_google(settings: Settings, model: str, texts: list[str]) -> list[list[float]]:
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY es requerido para embeddings Google")
    base_url = (settings.llm_base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model_path = model if model.startswith("models/") else f"models/{model}"
    timeout = httpx.Timeout(settings.llm_timeout_s)
    vectors: list[list[float]] = []
    with httpx.Client(timeout=timeout) as client:
        for text in texts:
            response = client.post(
                f"{base_url}/{model_path}:embedContent",
                headers={"x-goog-api-key": settings.llm_api_key},
                json={"content": {"parts": [{"text": text}]}},
            )
            response.raise_for_status()
            payload = response.json()
            values = (((payload.get("embedding") or {}).get("values")) or [])
            vectors.append([float(value) for value in values])
    return vectors


def _embed_ollama(settings: Settings, model: str, texts: list[str]) -> list[list[float]]:
    base_url = (settings.llm_base_url or "http://localhost:11434").rstrip("/")
    timeout = httpx.Timeout(settings.llm_timeout_s)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{base_url}/api/embed",
            json={"model": model, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
    vectors = payload.get("embeddings")
    if isinstance(vectors, list) and vectors:
        return [[float(value) for value in vector] for vector in vectors]

    # Compat con runtimes viejos de Ollama que no soportan batch.
    vectors = []
    with httpx.Client(timeout=timeout) as client:
        for text in texts:
            response = client.post(
                f"{base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            vector = payload.get("embedding") or []
            vectors.append([float(value) for value in vector])
    return vectors


def _resize_embeddings(vectors: list[list[float]], dim: int) -> list[list[float]]:
    normalized: list[list[float]] = []
    for vector in vectors:
        if len(vector) == dim:
            normalized.append(vector)
            continue
        if len(vector) > dim:
            normalized.append(vector[:dim])
            continue
        normalized.append(vector + [0.0] * (dim - len(vector)))
    return normalized


def _default_embedding_model(provider: str) -> str:
    if provider == "openai":
        return "text-embedding-3-small"
    if provider in {"google", "google_ai_studio", "gemini"}:
        return "text-embedding-004"
    if provider == "ollama":
        return "nomic-embed-text"
    return "stub"


def _deterministic_embeddings(texts: list[str], dim: int) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for text in texts:
        seed = sum(ord(char) for char in text)
        rng = random.Random(seed)
        embeddings.append([rng.random() for _ in range(dim)])
    return embeddings
