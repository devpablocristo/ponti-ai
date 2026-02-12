from types import SimpleNamespace

from adapters.outbound.rag.embeddings import resolve_embedding_provider_model


def test_resolve_embedding_provider_model_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")
    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    settings = SimpleNamespace(llm_provider="stub")

    provider, model = resolve_embedding_provider_model(settings)

    assert provider == "ollama"
    assert model == "nomic-embed-text"


def test_resolve_embedding_provider_model_falls_back_to_defaults(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    settings = SimpleNamespace(llm_provider="openai")

    provider, model = resolve_embedding_provider_model(settings)

    assert provider == "openai"
    assert model == "text-embedding-3-small"
