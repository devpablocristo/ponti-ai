import os
from dataclasses import dataclass

from application.insights.ports.baseline_computer import CohortConfig


@dataclass(frozen=True)
class Settings:
    # Config general
    app_name: str
    env: str

    # DB
    db_dsn: str

    # Seguridad y limites
    statement_timeout_ms: int
    max_limit: int
    default_limit: int

    # RAG
    embedding_dim: int
    rag_top_k: int

    # LLM
    llm_provider: str
    llm_model: str
    llm_api_key: str | None
    llm_base_url: str | None
    llm_timeout_s: float
    llm_max_retries: int

    # Insights
    insights_ratio_high: float
    insights_ratio_medium: float
    insights_spike_ratio: float
    insights_cooldown_days: int
    insights_impact_k: float
    insights_impact_cap: float

    # Baselines y jobs
    insights_size_small_max: float
    insights_size_medium_max: float
    insights_project_baseline_days: int
    insights_min_samples_project: int
    insights_baseline_lock_key: int
    insights_recompute_lock_key: int
    insights_baseline_batch_size: int
    insights_recompute_debounce_seconds: int
    insights_recompute_queue_batch_size: int
    insights_recompute_queue_workers: int
    insights_recompute_stale_lock_seconds: int

    # Planner v2 (LLM)
    domain: str
    max_actions_allowed: int

    # ML (Machine Learning)
    ml_enabled: bool
    ml_model_type: str
    ml_retrain_lock_key: int
    ml_rollout_percent: int
    ml_enabled_project_ids: tuple[str, ...]
    ml_shadow_mode: bool
    ml_auto_promote: bool
    ml_auto_retrain_min_hours: int
    ml_promotion_min_alert_rate_improvement: float
    ml_promotion_min_samples_ratio: float

    @property
    def cohort_config(self) -> CohortConfig:
        return CohortConfig(
            size_small_max=self.insights_size_small_max,
            size_medium_max=self.insights_size_medium_max,
        )


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


def _get_optional_csv(name: str, default: str = "") -> tuple[str, ...]:
    raw = _get_optional(name, default)
    if raw is None:
        return tuple()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


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
        embedding_dim=_get_required_int("EMBEDDING_DIM"),
        rag_top_k=_get_required_int("RAG_TOP_K"),
        llm_provider=llm_provider,
        llm_model=_get_optional("LLM_MODEL", default_model) or default_model,
        llm_api_key=_get_optional("LLM_API_KEY"),
        llm_base_url=_get_optional("LLM_BASE_URL"),
        llm_timeout_s=_get_optional_float("LLM_TIMEOUT_S", 20.0),
        llm_max_retries=_get_optional_int("LLM_MAX_RETRIES", 3),
        insights_ratio_high=_get_required_float("INSIGHTS_RATIO_HIGH"),
        insights_ratio_medium=_get_required_float("INSIGHTS_RATIO_MEDIUM"),
        insights_spike_ratio=_get_required_float("INSIGHTS_SPIKE_RATIO"),
        insights_cooldown_days=_get_required_int("INSIGHTS_COOLDOWN_DAYS"),
        insights_impact_k=_get_required_float("INSIGHTS_IMPACT_K"),
        insights_impact_cap=_get_required_float("INSIGHTS_IMPACT_CAP"),
        insights_size_small_max=_get_required_float("INSIGHTS_SIZE_SMALL_MAX"),
        insights_size_medium_max=_get_required_float("INSIGHTS_SIZE_MEDIUM_MAX"),
        insights_project_baseline_days=_get_required_int("INSIGHTS_PROJECT_BASELINE_DAYS"),
        insights_min_samples_project=_get_required_int("INSIGHTS_MIN_SAMPLES_PROJECT"),
        insights_baseline_lock_key=_get_required_int("INSIGHTS_BASELINE_LOCK_KEY"),
        insights_recompute_lock_key=_get_required_int("INSIGHTS_RECOMPUTE_LOCK_KEY"),
        insights_baseline_batch_size=_get_required_int("INSIGHTS_BASELINE_BATCH_SIZE"),
        insights_recompute_debounce_seconds=max(0, _get_optional_int("INSIGHTS_RECOMPUTE_DEBOUNCE_SECONDS", 120)),
        insights_recompute_queue_batch_size=max(1, _get_optional_int("INSIGHTS_RECOMPUTE_QUEUE_BATCH_SIZE", 50)),
        insights_recompute_queue_workers=max(1, _get_optional_int("INSIGHTS_RECOMPUTE_QUEUE_WORKERS", 4)),
        insights_recompute_stale_lock_seconds=max(30, _get_optional_int("INSIGHTS_RECOMPUTE_STALE_LOCK_SECONDS", 300)),
        domain=_get_optional("DOMAIN", "agriculture") or "agriculture",
        max_actions_allowed=_get_optional_int("MAX_ACTIONS_ALLOWED", 4),
        ml_enabled=_get_optional("ML_ENABLED", "false") == "true",
        ml_model_type=_get_optional("ML_MODEL_TYPE", "isolation_forest") or "isolation_forest",
        ml_retrain_lock_key=_get_optional_int("ML_RETRAIN_LOCK_KEY", 41003),
        ml_rollout_percent=max(0, min(100, _get_optional_int("ML_ROLLOUT_PERCENT", 100))),
        ml_enabled_project_ids=_get_optional_csv("ML_ENABLED_PROJECT_IDS", ""),
        ml_shadow_mode=_get_optional("ML_SHADOW_MODE", "false") == "true",
        ml_auto_promote=_get_optional("ML_AUTO_PROMOTE", "true") == "true",
        ml_auto_retrain_min_hours=max(1, _get_optional_int("ML_AUTO_RETRAIN_MIN_HOURS", 24)),
        ml_promotion_min_alert_rate_improvement=max(0.0, _get_optional_float("ML_PROMOTION_MIN_ALERT_RATE_IMPROVEMENT", 0.01)),
        ml_promotion_min_samples_ratio=max(0.0, _get_optional_float("ML_PROMOTION_MIN_SAMPLES_RATIO", 0.8)),
    )
