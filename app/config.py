import os
from dataclasses import dataclass


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
    )
