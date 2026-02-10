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
        llm_model="stub",
        llm_api_key=None,
        llm_base_url=None,
        llm_timeout_s=5.0,
        llm_max_retries=1,
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
        insights_recompute_debounce_seconds=120,
        insights_recompute_queue_batch_size=50,
        insights_recompute_queue_workers=4,
        insights_recompute_stale_lock_seconds=300,
        domain="agriculture",
        max_actions_allowed=4,
        ml_enabled=False,
        ml_model_type="isolation_forest",
        ml_retrain_lock_key=41003,
        ml_rollout_percent=100,
        ml_enabled_project_ids=(),
        ml_shadow_mode=False,
        ml_auto_promote=True,
        ml_auto_retrain_min_hours=24,
        ml_promotion_min_alert_rate_improvement=0.01,
        ml_promotion_min_samples_ratio=0.8,
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
