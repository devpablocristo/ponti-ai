import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str
    env: str
    db_dsn: str
    statement_timeout_ms: int
    max_limit: int
    default_limit: int
    llm_provider: str
    llm_model: str
    llm_api_key: str | None
    llm_base_url: str | None
    llm_timeout_ms: int
    llm_max_retries: int
    llm_max_output_tokens: int
    llm_max_calls_per_request: int
    llm_budget_tokens_per_request: int
    llm_rate_limit_rps: float
    copilot_enabled: bool
    insights_ratio_high: float
    insights_ratio_medium: float
    insights_spike_ratio: float
    insights_cooldown_days: int
    insights_impact_k: float
    insights_impact_cap: float
    insights_size_small_max: float
    insights_size_medium_max: float
    domain: str
    max_actions_allowed: int


def _get_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} es requerido")
    return value


def _get_optional(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip()
    return value if value else default


def _get_required_int(name: str) -> int:
    raw = _get_required(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser numerico") from exc


def _get_optional_int(name: str, default: int) -> int:
    raw = _get_optional(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser numerico") from exc


def _get_required_float(name: str) -> float:
    raw = _get_required(name)
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser numerico") from exc


def _get_optional_float(name: str, default: float) -> float:
    raw = _get_optional(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser numerico") from exc


def _get_optional_bool(name: str, default: bool) -> bool:
    raw = _get_optional(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} debe ser booleano")


def load_settings() -> Settings:
    llm_provider = _get_required("LLM_PROVIDER")
    provider_norm = llm_provider.strip().lower()
    default_model = "gpt-4o-mini"
    if provider_norm == "stub":
        default_model = "stub"
    elif provider_norm in {"google", "google_ai_studio", "gemini"}:
        default_model = "gemini-flash-latest"
    elif provider_norm in {"ollama"}:
        default_model = "llama3.1"

    return Settings(
        app_name=_get_required("APP_NAME"),
        env=_get_required("APP_ENV"),
        db_dsn=_get_required("DB_DSN"),
        statement_timeout_ms=_get_required_int("STATEMENT_TIMEOUT_MS"),
        max_limit=_get_required_int("MAX_LIMIT"),
        default_limit=_get_required_int("DEFAULT_LIMIT"),
        llm_provider=llm_provider,
        llm_model=_get_optional("LLM_MODEL", default_model) or default_model,
        llm_api_key=_get_optional("LLM_API_KEY"),
        llm_base_url=_get_optional("LLM_BASE_URL"),
        llm_timeout_ms=max(1, _get_optional_int("LLM_TIMEOUT_MS", 5000)),
        llm_max_retries=max(1, _get_optional_int("LLM_MAX_RETRIES", 3)),
        llm_max_output_tokens=max(1, _get_optional_int("LLM_MAX_OUTPUT_TOKENS", 700)),
        llm_max_calls_per_request=max(1, _get_optional_int("LLM_MAX_CALLS_PER_REQUEST", 3)),
        llm_budget_tokens_per_request=max(1, _get_optional_int("LLM_BUDGET_TOKENS_PER_REQUEST", 2500)),
        llm_rate_limit_rps=max(0.1, _get_optional_float("LLM_RATE_LIMIT_RPS", 2.0)),
        copilot_enabled=_get_optional_bool("COPILOT_ENABLED", True),
        insights_ratio_high=_get_required_float("INSIGHTS_RATIO_HIGH"),
        insights_ratio_medium=_get_required_float("INSIGHTS_RATIO_MEDIUM"),
        insights_spike_ratio=_get_required_float("INSIGHTS_SPIKE_RATIO"),
        insights_cooldown_days=_get_required_int("INSIGHTS_COOLDOWN_DAYS"),
        insights_impact_k=_get_required_float("INSIGHTS_IMPACT_K"),
        insights_impact_cap=_get_required_float("INSIGHTS_IMPACT_CAP"),
        insights_size_small_max=_get_required_float("INSIGHTS_SIZE_SMALL_MAX"),
        insights_size_medium_max=_get_required_float("INSIGHTS_SIZE_MEDIUM_MAX"),
        domain=_get_optional("DOMAIN", "agriculture") or "agriculture",
        max_actions_allowed=max(0, _get_optional_int("MAX_ACTIONS_ALLOWED", 4)),
    )
