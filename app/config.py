from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from core_ai.config.llm import resolve_model_name, validate_provider_api_key


class Settings(BaseSettings):
    """
    Configuración central del servicio.

    - env_ignore_empty=True: si una env var está vacía (ej. LLM_API_KEY=)
      se trata como "no seteada" y usa el default del campo.
    - env_file='.env': carga .env solo para desarrollo local.
    - Las validaciones de campos requeridos las hace Pydantic automáticamente.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str
    app_env: str
    db_dsn: str
    statement_timeout_ms: int
    max_limit: int
    default_limit: int

    # --- Copilot / LLM ---
    copilot_enabled: bool = True
    llm_provider: str = "stub"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_timeout_ms: int = 5000
    llm_max_retries: int = 3
    llm_max_output_tokens: int = 700
    llm_max_calls_per_request: int = 3
    llm_budget_tokens_per_request: int = 2500
    llm_rate_limit_rps: float = 2.0

    # --- Insights (reglas determinísticas) ---
    insights_ratio_high: float
    insights_ratio_medium: float
    insights_spike_ratio: float
    insights_cooldown_days: int
    insights_impact_k: float
    insights_impact_cap: float
    insights_size_small_max: float
    insights_size_medium_max: float

    # --- Domain ---
    domain: str = "agriculture"
    max_actions_allowed: int = 4

    # -- Guards: clamp mínimos para evitar valores absurdos --

    @field_validator("llm_timeout_ms")
    @classmethod
    def _clamp_timeout(cls, v: int) -> int:
        return max(1, v)

    @field_validator("llm_max_retries")
    @classmethod
    def _clamp_retries(cls, v: int) -> int:
        return max(1, v)

    @field_validator("llm_max_output_tokens")
    @classmethod
    def _clamp_output_tokens(cls, v: int) -> int:
        return max(1, v)

    @field_validator("llm_max_calls_per_request")
    @classmethod
    def _clamp_calls(cls, v: int) -> int:
        return max(1, v)

    @field_validator("llm_budget_tokens_per_request")
    @classmethod
    def _clamp_budget(cls, v: int) -> int:
        return max(1, v)

    @field_validator("llm_rate_limit_rps")
    @classmethod
    def _clamp_rps(cls, v: float) -> float:
        return max(0.1, v)

    @field_validator("max_actions_allowed")
    @classmethod
    def _clamp_max_actions(cls, v: int) -> int:
        return max(0, v)

    # -- Validaciones post-init --

    @model_validator(mode="after")
    def _resolve_model_and_validate_provider(self) -> "Settings":
        object.__setattr__(self, "llm_model", resolve_model_name(self.llm_provider, self.llm_model))
        validate_provider_api_key(
            self.llm_provider,
            self.llm_api_key,
            enabled=self.copilot_enabled,
            error_message="LLM_API_KEY es requerido cuando COPILOT_ENABLED=true y LLM_PROVIDER requiere key",
        )

        return self


# Retrocompatibilidad: load_settings() para app/main.py
def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
