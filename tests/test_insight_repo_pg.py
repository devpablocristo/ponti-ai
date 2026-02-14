import pytest

from adapters.outbound.db.repos.insight_repo_pg import InsightRepositoryPG
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        app_name="test",
        env="test",
        db_dsn="postgresql://unused",
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


def test_get_by_id_invalid_uuid_returns_none_without_db_hit() -> None:
    repo = InsightRepositoryPG(_settings())

    class _FailSession:
        def connect(self):  # type: ignore[no-untyped-def]
            raise AssertionError("db should not be called")

    repo.session = _FailSession()  # type: ignore[assignment]
    assert repo.get_by_id("p1", "not-found") is None


def test_record_action_invalid_uuid_raises_value_error_without_db_hit() -> None:
    repo = InsightRepositoryPG(_settings())

    class _FailSession:
        def connect(self):  # type: ignore[no-untyped-def]
            raise AssertionError("db should not be called")

    repo.session = _FailSession()  # type: ignore[assignment]
    with pytest.raises(ValueError):
        repo.record_action("not-found", "p1", "u1", "ack", "acknowledged")
