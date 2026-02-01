import pytest

from app.config import Settings
from adapters.outbound.sql.executor import SQLExecutor


def test_executor_requires_dsn() -> None:
    settings = Settings(
        app_name="test",
        env="test",
        db_dsn="",
        statement_timeout_ms=1000,
        max_limit=10,
        default_limit=5,
        embedding_dim=8,
        rag_top_k=3,
        llm_provider="stub",
    )
    executor = SQLExecutor(settings)
    with pytest.raises(ValueError):
        executor.execute(
            sql_template="SELECT %(project_id)s::text AS project_id LIMIT %(limit)s",
            params={"project_id": "p-1"},
            statement_timeout_ms=1000,
            max_limit=10,
            default_limit=5,
        )
