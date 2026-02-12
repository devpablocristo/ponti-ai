from types import SimpleNamespace

from adapters.inbound.api.auth.headers import AuthContext
from adapters.inbound.api.routes.jobs import retrain_ml
from adapters.inbound.api.routes.ml import ml_activate, ml_rollback, ml_status
from adapters.inbound.api.schemas.insights import JobRetrainMLRequest, MLActivateRequest, MLRollbackRequest


class FakeJobLock:
    def __init__(self, can_lock: bool = True) -> None:
        self.can_lock = can_lock
        self.released = False

    def try_lock(self, key: int) -> bool:
        _ = key
        return self.can_lock

    def release(self, key: int) -> None:
        _ = key
        self.released = True


class FakeModelInfo:
    def __init__(self, version: str) -> None:
        self.version = version


class FakeTrainResult:
    def __init__(self, version: str, training_time_seconds: float, metrics: dict[str, float]) -> None:
        self.model_info = FakeModelInfo(version)
        self.training_time_seconds = training_time_seconds
        self.metrics = metrics


class FakeMLFacade:
    def __init__(self, fail_train: bool = False) -> None:
        self.fail_train = fail_train
        self.last_train_args: dict | None = None
        self.last_policy_args: dict | None = None

    def get_status(self) -> dict:
        return {
            "enabled": True,
            "model_type": "isolation_forest",
            "models_dir": "/app/contexts/ml_models",
            "has_active_model": True,
            "active_version": "v1",
            "available_versions": ["v1"],
            "active_history": ["v1"],
        }

    def train(self, version: str | None = None, activate: bool = False, hyperparameters: dict | None = None):
        self.last_train_args = {
            "version": version,
            "activate": activate,
            "hyperparameters": hyperparameters,
        }
        if self.fail_train:
            raise RuntimeError("train_failed")
        return FakeTrainResult(version or "v-auto", 1.2, {"anomaly_rate": 0.1})

    def retrain_with_policy(
        self,
        version: str | None = None,
        hyperparameters: dict | None = None,
        auto_promote: bool | None = None,
        force_activate: bool = False,
    ) -> dict:
        self.last_policy_args = {
            "version": version,
            "hyperparameters": hyperparameters,
            "auto_promote": auto_promote,
            "force_activate": force_activate,
        }
        if self.fail_train:
            raise RuntimeError("train_failed")
        return {
            "status": "ok",
            "model_version": version or "v-auto",
            "active_version": version or "v-auto",
            "training_time_seconds": 1.2,
            "metrics": {"anomaly_rate": 0.1},
            "promoted": True,
            "promotion_reason": "forced_activate" if force_activate else "better_alert_rate_calibration",
        }

    def activate_version(self, version: str) -> dict:
        return {
            "status": "ok",
            "previous_active_version": "v1",
            "active_version": version,
        }

    def rollback_version(self, target_version: str | None = None) -> dict:
        return {
            "status": "ok",
            "previous_active_version": "v2",
            "active_version": target_version or "v1",
            "rollback_target_version": target_version or "v1",
        }


def _auth() -> AuthContext:
    return AuthContext(api_key="k", user_id="u1", project_id="p1")


def test_ml_status_when_ml_unavailable() -> None:
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_enabled=False, ml_model_type="isolation_forest"),
        ml_facade=None,
    )
    result = ml_status(auth=_auth(), container=container)
    assert result.initialized is False
    assert result.has_active_model is False


def test_ml_status_when_ml_available() -> None:
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_enabled=True, ml_model_type="isolation_forest"),
        ml_facade=FakeMLFacade(),
    )
    result = ml_status(auth=_auth(), container=container)
    assert result.initialized is True
    assert result.active_version == "v1"
    assert result.available_versions == ["v1"]
    assert result.active_history == ["v1"]


def test_ml_activate_ok() -> None:
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_enabled=True, ml_model_type="isolation_forest", ml_shadow_mode=False),
        ml_facade=FakeMLFacade(),
    )
    result = ml_activate(req=MLActivateRequest(version="v2"), auth=_auth(), container=container)
    assert result.status == "ok"
    assert result.active_version == "v2"


def test_ml_rollback_ok() -> None:
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_enabled=True, ml_model_type="isolation_forest", ml_shadow_mode=False),
        ml_facade=FakeMLFacade(),
    )
    result = ml_rollback(req=MLRollbackRequest(target_version="v1"), auth=_auth(), container=container)
    assert result.status == "ok"
    assert result.rollback_target_version == "v1"


def test_retrain_ml_locked() -> None:
    lock = FakeJobLock(can_lock=False)
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_retrain_lock_key=41003),
        ml_facade=FakeMLFacade(),
        job_lock=lock,
    )
    result = retrain_ml(req=JobRetrainMLRequest(), auth=_auth(), container=container)
    assert result.status == "locked"
    assert result.job_run_id == ""


def test_retrain_ml_ok() -> None:
    lock = FakeJobLock(can_lock=True)
    facade = FakeMLFacade()
    container = SimpleNamespace(
        settings=SimpleNamespace(ml_retrain_lock_key=41003),
        ml_facade=facade,
        job_lock=lock,
    )
    req = JobRetrainMLRequest(
        version="v2_manual",
        activate=True,
        hyperparameters={"contamination": 0.07, "n_estimators": 200},
    )
    result = retrain_ml(req=req, auth=_auth(), container=container)
    assert result.status == "ok"
    assert result.model_version == "v2_manual"
    assert lock.released is True
    assert facade.last_policy_args == {
        "version": "v2_manual",
        "hyperparameters": {"contamination": 0.07, "n_estimators": 200},
        "auto_promote": True,
        "force_activate": True,
    }
