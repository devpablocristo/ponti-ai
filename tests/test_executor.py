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
        insights_ratio_high=0.5,
        insights_ratio_medium=0.2,
        insights_spike_ratio=1.5,
        insights_cooldown_days=7,
        insights_impact_k=1.0,
        insights_impact_cap=2.0,
        insights_size_small_max=200,
        insights_size_medium_max=1000,
        insights_project_baseline_days=365,
        insights_min_samples_project=10,
        insights_baseline_lock_key=41001,
        insights_recompute_lock_key=41002,
        insights_baseline_batch_size=200,
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
