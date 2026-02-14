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
        llm_provider="stub",
        llm_model="stub",
        llm_api_key=None,
        llm_base_url=None,
        llm_timeout_ms=5000,
        llm_max_retries=1,
        llm_max_output_tokens=700,
        llm_max_calls_per_request=3,
        llm_budget_tokens_per_request=2500,
        llm_rate_limit_rps=2.0,
        copilot_enabled=True,
        insights_ratio_high=0.5,
        insights_ratio_medium=0.2,
        insights_spike_ratio=1.5,
        insights_cooldown_days=7,
        insights_impact_k=1.0,
        insights_impact_cap=2.0,
        insights_size_small_max=200,
        insights_size_medium_max=1000,
        domain="agriculture",
        max_actions_allowed=4,
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
