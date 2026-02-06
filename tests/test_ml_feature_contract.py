from datetime import datetime, timezone

import pytest

pytest.importorskip("joblib")

from ml.adapters.training.postgres_data_loader import PostgresDataLoader
from ml.config import load_ml_config
from ml.facade import MLFacade
from ml.domain.entities import ModelInfo
from application.insights.ports.feature_repository import FeatureValue


def _contract(config) -> list[str]:
    return [
        f"{feature_name}_{window}"
        for feature_name in config.features.feature_names
        for window in config.features.windows
    ]


def test_loader_rows_to_dataset_applies_contract_with_zero_fill() -> None:
    config = load_ml_config()
    loader = PostgresDataLoader(dsn="postgresql://unused", ml_config=config)
    columns = ["project_id", "feature_name", "value"]
    rows = [
        ("1", "cost_total_all", 1200.0),
        ("1", "workorders_count_last_7d", 8.0),
        ("2", "cost_total_all", 600.0),
    ]

    dataset = loader._rows_to_dataset(rows, columns)
    contract = _contract(config)

    assert set(dataset.features.keys()) == set(contract)
    assert dataset.sample_ids == ("1", "2")
    assert dataset.features["cost_total_all"] == [1200.0, 600.0]
    assert dataset.features["workorders_count_last_7d"] == [8.0, 0.0]
    assert dataset.features["stock_variance_last_30d"] == [0.0, 0.0]


def test_ml_facade_features_to_dataset_uses_contract() -> None:
    config = load_ml_config()
    facade = MLFacade(config, db_dsn="postgresql://unused")
    features = [
        FeatureValue(
            project_id="1",
            entity_type="project",
            entity_id="1",
            feature_name="cost_total",
            window="all",
            value=500.0,
        ),
        FeatureValue(
            project_id="1",
            entity_type="project",
            entity_id="1",
            feature_name="workorders_count",
            window="last_7d",
            value=4.0,
        ),
    ]

    dataset = facade._features_to_dataset(project_id="1", features=features)
    contract = _contract(config)

    assert list(dataset.features.keys()) == contract
    assert dataset.features["cost_total_all"] == [500.0]
    assert dataset.features["workorders_count_last_7d"] == [4.0]
    assert dataset.features["inputs_total_used_last_30d"] == [0.0]


def test_ml_facade_rollout_hash_gate() -> None:
    config = load_ml_config()
    facade = MLFacade(config, db_dsn="postgresql://unused", rollout_percent=0)
    assert facade._is_project_enabled_for_ml("project-1") is False

    facade_all = MLFacade(config, db_dsn="postgresql://unused", rollout_percent=100)
    assert facade_all._is_project_enabled_for_ml("project-1") is True


def test_ml_facade_estimate_drift() -> None:
    config = load_ml_config()
    facade = MLFacade(config, db_dsn="postgresql://unused")
    dataset = facade._features_to_dataset(
        project_id="1",
        features=[
            FeatureValue(
                project_id="1",
                entity_type="project",
                entity_id="1",
                feature_name="cost_total",
                window="all",
                value=1000.0,
            )
        ],
    )
    metrics = {
        "profile_mean_cost_total_all": 100.0,
        "profile_std_cost_total_all": 10.0,
    }
    model_info = ModelInfo(
        model_id="isolation_forest",
        model_type="isolation_forest",
        version="v1",
        trained_at=datetime.now(timezone.utc),
        n_samples_trained=100,
        hyperparameters={},
        feature_names=tuple(dataset.features.keys()),
        metrics=metrics,
        is_active=True,
    )
    drift = facade._estimate_drift(dataset, model_info)
    assert drift["level"] in {"medium", "high"}
