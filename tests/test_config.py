import pytest
from pydantic import ValidationError

from app.config import Settings


def _base_env(monkeypatch) -> None:
    """Setea las env vars mínimas requeridas para construir Settings."""
    monkeypatch.setenv("APP_NAME", "test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DB_DSN", "postgresql://unused")
    monkeypatch.setenv("STATEMENT_TIMEOUT_MS", "1000")
    monkeypatch.setenv("MAX_LIMIT", "100")
    monkeypatch.setenv("DEFAULT_LIMIT", "50")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("INSIGHTS_RATIO_HIGH", "0.5")
    monkeypatch.setenv("INSIGHTS_RATIO_MEDIUM", "0.2")
    monkeypatch.setenv("INSIGHTS_SPIKE_RATIO", "1.5")
    monkeypatch.setenv("INSIGHTS_COOLDOWN_DAYS", "7")
    monkeypatch.setenv("INSIGHTS_IMPACT_K", "1.0")
    monkeypatch.setenv("INSIGHTS_IMPACT_CAP", "2.0")
    monkeypatch.setenv("INSIGHTS_SIZE_SMALL_MAX", "200")
    monkeypatch.setenv("INSIGHTS_SIZE_MEDIUM_MAX", "1000")


# --- env_ignore_empty ---


def test_empty_llm_api_key_is_none(monkeypatch) -> None:
    """LLM_API_KEY='' (vacío) debe tratarse como None gracias a env_ignore_empty."""
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_API_KEY", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_api_key is None


def test_empty_llm_model_resolves_auto(monkeypatch) -> None:
    """LLM_MODEL='' debe auto-resolverse por provider."""
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_MODEL", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_model == "stub"  # porque LLM_PROVIDER=stub


def test_empty_domain_uses_default(monkeypatch) -> None:
    """DOMAIN='' debe usar el default 'agriculture'."""
    _base_env(monkeypatch)
    monkeypatch.setenv("DOMAIN", "")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.domain == "agriculture"


# --- Requeridas faltan ---


def test_missing_required_app_name_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.delenv("APP_NAME")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "app_name" in str(exc_info.value).lower()


def test_missing_required_db_dsn_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.delenv("DB_DSN")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "db_dsn" in str(exc_info.value).lower()


def test_missing_required_insights_raises(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.delenv("INSIGHTS_RATIO_HIGH")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


# --- Auto-resolve LLM_MODEL por provider ---


def test_llm_model_auto_openai(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_model == "gpt-4o-mini"


def test_llm_model_auto_google(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "google_ai_studio")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_model == "gemini-flash-latest"


def test_llm_model_auto_ollama(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_API_KEY", "unused")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_model == "llama3.1"


def test_llm_model_explicit_overrides_auto(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_model == "gpt-4o"


# --- Validación condicional: copilot + provider ---


def test_copilot_enabled_non_stub_requires_api_key(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    # No seteamos LLM_API_KEY → debe fallar
    with pytest.raises(ValidationError, match="LLM_API_KEY"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_copilot_disabled_no_api_key_ok(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    # Sin API key pero copilot disabled → OK
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.copilot_enabled is False


def test_copilot_enabled_stub_no_api_key_ok(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.copilot_enabled is True
    assert s.llm_api_key is None


# --- Guards / clamps ---


def test_clamps_enforce_minimums(monkeypatch) -> None:
    _base_env(monkeypatch)
    monkeypatch.setenv("LLM_TIMEOUT_MS", "0")
    monkeypatch.setenv("LLM_MAX_RETRIES", "-1")
    monkeypatch.setenv("LLM_RATE_LIMIT_RPS", "0.01")
    monkeypatch.setenv("MAX_ACTIONS_ALLOWED", "-5")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.llm_timeout_ms >= 1
    assert s.llm_max_retries >= 1
    assert s.llm_rate_limit_rps >= 0.1
    assert s.max_actions_allowed >= 0


# --- Defaults correctos ---


def test_defaults_applied(monkeypatch) -> None:
    _base_env(monkeypatch)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.copilot_enabled is True
    assert s.llm_timeout_ms == 5000
    assert s.llm_max_retries == 3
    assert s.llm_max_output_tokens == 700
    assert s.llm_max_calls_per_request == 3
    assert s.llm_budget_tokens_per_request == 2500
    assert s.llm_rate_limit_rps == 2.0
    assert s.domain == "agriculture"
    assert s.max_actions_allowed == 4
