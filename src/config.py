from __future__ import annotations

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from runtime.config.llm import resolve_model_name, validate_provider_api_key


class Settings(BaseSettings):
    """
    Configuración central del servicio.

    - env_ignore_empty=True: si una env var está vacía (ej. LLM_API_KEY=)
      se trata como "no seteada" y usa el default del campo.
    - env_file='.env': carga .env solo para desarrollo local.
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
    ai_service_keys: str
    statement_timeout_ms: int
    max_limit: int
    default_limit: int

    # --- Insight Chat / LLM ---
    insight_chat_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("INSIGHT_CHAT_ENABLED", "COPILOT_ENABLED"),
    )
    chat_enabled: bool = True
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

    # --- Ponti backend (lecturas para tools del chat; opcional) ---
    ponti_backend_base_url: str | None = None
    ponti_backend_api_key: str | None = None
    ponti_backend_timeout_ms: int = 15000
    ponti_backend_max_response_chars: int = 16000
    ponti_backend_authorization: str | None = None
    ponti_backend_tenant_id: str | None = None
    ponti_backend_tenant_header: str = "X-Tenant-Id"

    # --- Chat ---
    chat_max_tool_calls: int = 14
    chat_project_context_ttl_seconds: int = 900
    chat_dashboard_context_ttl_seconds: int = 600

    # -- Guards --

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

    @field_validator("ponti_backend_timeout_ms")
    @classmethod
    def _clamp_backend_timeout(cls, v: int) -> int:
        return max(500, v)

    @field_validator("ponti_backend_max_response_chars")
    @classmethod
    def _clamp_backend_json(cls, v: int) -> int:
        return max(2000, v)

    @field_validator("chat_max_tool_calls")
    @classmethod
    def _clamp_chat_tools(cls, v: int) -> int:
        return max(1, min(v, 40))

    @field_validator("chat_project_context_ttl_seconds", "chat_dashboard_context_ttl_seconds")
    @classmethod
    def _clamp_context_ttl(cls, v: int) -> int:
        return max(60, min(v, 86_400))

    @model_validator(mode="after")
    def _resolve_model_and_validate_provider(self) -> "Settings":
        object.__setattr__(self, "llm_model", resolve_model_name(self.llm_provider, self.llm_model))
        validate_provider_api_key(
            self.llm_provider,
            self.llm_api_key,
            enabled=self.insight_chat_enabled,
            error_message="LLM_API_KEY es requerido cuando INSIGHT_CHAT_ENABLED=true y LLM_PROVIDER requiere key",
        )
        return self


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
