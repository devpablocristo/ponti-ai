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


def _get_required_int(name: str) -> int:
    raw = _get_required(name)
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


def load_settings() -> Settings:
    return Settings(
        app_name=_get_required("APP_NAME"),
        env=_get_required("APP_ENV"),
        db_dsn=_get_required("DB_DSN"),
        statement_timeout_ms=_get_required_int("STATEMENT_TIMEOUT_MS"),
        max_limit=_get_required_int("MAX_LIMIT"),
        default_limit=_get_required_int("DEFAULT_LIMIT"),
        embedding_dim=_get_required_int("EMBEDDING_DIM"),
        rag_top_k=_get_required_int("RAG_TOP_K"),
        llm_provider=_get_required("LLM_PROVIDER"),
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
    )
