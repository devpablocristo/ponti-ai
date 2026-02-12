from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
    MLActivateRequest,
    MLRollbackRequest,
    MLStatusResponse,
    MLVersionChangeResponse,
)

router = APIRouter()
HANDLED_ML_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


@router.get("/v1/ml/status", response_model=MLStatusResponse)
def ml_status(
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> MLStatusResponse:
    _ = auth

    if container.ml_facade is None:
        return MLStatusResponse(
            enabled=bool(container.settings.ml_enabled),
            initialized=False,
            model_type=container.settings.ml_model_type,
            models_dir=None,
            has_active_model=False,
            active_version=None,
            available_versions=[],
            rollout_percent=int(getattr(container.settings, "ml_rollout_percent", 100)),
            rollout_allowlist_size=len(getattr(container.settings, "ml_enabled_project_ids", ()) or ()),
            last_drift_score=None,
            last_drift_level=None,
            shadow_mode=bool(getattr(container.settings, "ml_shadow_mode", False)),
            active_history=[],
            auto_promote=bool(getattr(container.settings, "ml_auto_promote", True)),
            auto_retrain_min_hours=int(getattr(container.settings, "ml_auto_retrain_min_hours", 24)),
        )

    status = container.ml_facade.get_status()
    return MLStatusResponse(
        enabled=bool(status.get("enabled", False)),
        initialized=True,
        model_type=str(status.get("model_type", container.settings.ml_model_type)),
        models_dir=str(status.get("models_dir", "")) or None,
        has_active_model=bool(status.get("has_active_model", False)),
        active_version=status.get("active_version"),
        available_versions=[str(v) for v in status.get("available_versions", [])],
        rollout_percent=int(status.get("rollout_percent", 100)),
        rollout_allowlist_size=int(status.get("rollout_allowlist_size", 0)),
        last_drift_score=(
            float(status["last_drift_score"])
            if status.get("last_drift_score") is not None
            else None
        ),
        last_drift_level=(
            str(status["last_drift_level"])
            if status.get("last_drift_level") is not None
            else None
        ),
        shadow_mode=bool(getattr(container.settings, "ml_shadow_mode", False)),
        active_history=[str(v) for v in status.get("active_history", [])],
        auto_promote=bool(status.get("auto_promote", getattr(container.settings, "ml_auto_promote", True))),
        auto_retrain_min_hours=int(
            status.get("auto_retrain_min_hours", getattr(container.settings, "ml_auto_retrain_min_hours", 24))
        ),
    )


@router.post("/v1/ml/activate", response_model=MLVersionChangeResponse)
def ml_activate(
    req: MLActivateRequest,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> MLVersionChangeResponse:
    _ = auth
    if container.ml_facade is None:
        return MLVersionChangeResponse(
            status="ml_unavailable",
            error="ML facade no inicializado",
        )
    try:
        result = container.ml_facade.activate_version(req.version)
        return MLVersionChangeResponse(
            status=str(result.get("status", "ok")),
            previous_active_version=result.get("previous_active_version"),
            active_version=result.get("active_version"),
            rollback_target_version=None,
            error=None,
        )
    except HANDLED_ML_ERRORS as exc:
        return MLVersionChangeResponse(
            status="error",
            error=str(exc),
        )


@router.post("/v1/ml/rollback", response_model=MLVersionChangeResponse)
def ml_rollback(
    req: MLRollbackRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> MLVersionChangeResponse:
    _ = auth
    if container.ml_facade is None:
        return MLVersionChangeResponse(
            status="ml_unavailable",
            error="ML facade no inicializado",
        )
    try:
        result = container.ml_facade.rollback_version(req.target_version if req else None)
        return MLVersionChangeResponse(
            status=str(result.get("status", "ok")),
            previous_active_version=result.get("previous_active_version"),
            active_version=result.get("active_version"),
            rollback_target_version=result.get("rollback_target_version"),
            error=None,
        )
    except HANDLED_ML_ERRORS as exc:
        return MLVersionChangeResponse(
            status="error",
            error=str(exc),
        )
