import time
import uuid

from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
    JobRetrainMLRequest,
    JobRetrainMLResponse,
    JobRecomputeBaselinesRequest,
    JobRecomputeBaselinesResponse,
    JobRecomputeRequest,
)
from adapters.outbound.observability.logging import log_event
from adapters.outbound.observability.metrics import inc_counter, observe_ms

router = APIRouter()


@router.post("/v1/jobs/recompute-active")
def recompute_active(
    req: JobRecomputeRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> dict[str, str]:
    started = time.time()
    result = container.recompute_active.handle(
        project_id=auth.project_id,
        lock_key=container.settings.insights_recompute_lock_key,
        batch_size=req.batch_size if req else None,
    )
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("jobs.recompute.duration_ms", duration_ms)
    inc_counter("jobs.recompute.count", 1)
    log_event(
        "jobs.recompute",
        {
            "project_id": auth.project_id,
            "status": result["status"],
            "job_run_id": result["job_run_id"],
        },
    )
    return {"status": result["status"], "job_run_id": result["job_run_id"]}


@router.post("/v1/jobs/recompute-baselines", response_model=JobRecomputeBaselinesResponse)
def recompute_baselines(
    req: JobRecomputeBaselinesRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> JobRecomputeBaselinesResponse:
    started = time.time()
    result = container.recompute_baselines.handle(
        project_id=auth.project_id,
        cohort=container.settings.cohort_config,
        baseline_days=container.settings.insights_project_baseline_days,
        min_samples=container.settings.insights_min_samples_project,
        batch_size=req.batch_size if req and req.batch_size else container.settings.insights_baseline_batch_size,
        lock_key=container.settings.insights_baseline_lock_key,
    )
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("jobs.baselines.duration_ms", duration_ms)
    inc_counter("jobs.baselines.count", 1)
    log_event(
        "jobs.baselines",
        {
            "project_id": auth.project_id,
            "status": result["status"],
            "job_run_id": result["job_run_id"],
        },
    )
    return JobRecomputeBaselinesResponse(
        status=str(result["status"]),
        job_run_id=str(result["job_run_id"]),
        cohort_saved=int(result.get("cohort_saved", 0)),
        project_saved=int(result.get("project_saved", 0)),
    )


@router.post("/v1/jobs/retrain-ml", response_model=JobRetrainMLResponse)
def retrain_ml(
    req: JobRetrainMLRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> JobRetrainMLResponse:
    if container.ml_facade is None:
        return JobRetrainMLResponse(
            status="ml_unavailable",
            job_run_id="",
            model_version=None,
            training_time_seconds=None,
            metrics={},
            error="ML facade no inicializado",
        )

    lock_key = container.settings.ml_retrain_lock_key
    if not container.job_lock.try_lock(lock_key):
        return JobRetrainMLResponse(
            status="locked",
            job_run_id="",
            model_version=None,
            training_time_seconds=None,
            metrics={},
            error=None,
        )

    started = time.time()
    job_run_id = str(uuid.uuid4())

    try:
        result = container.ml_facade.retrain_with_policy(
            version=req.version if req else None,
            hyperparameters=req.hyperparameters if req else None,
            auto_promote=req.auto_promote if req else bool(getattr(container.settings, "ml_auto_promote", True)),
            force_activate=bool(req.activate) if req else False,
        )
        duration_ms = int((time.time() - started) * 1000)
        observe_ms("jobs.retrain_ml.duration_ms", duration_ms)
        inc_counter("jobs.retrain_ml.count", 1)
        log_event(
            "jobs.retrain_ml",
            {
                "project_id": auth.project_id,
                "status": "ok",
                "job_run_id": job_run_id,
                "model_version": result.get("model_version"),
                "promoted": bool(result.get("promoted", False)),
                "promotion_reason": result.get("promotion_reason"),
            },
        )
        return JobRetrainMLResponse(
            status="ok",
            job_run_id=job_run_id,
            model_version=str(result.get("model_version")) if result.get("model_version") else None,
            active_version=str(result.get("active_version")) if result.get("active_version") else None,
            promoted=bool(result.get("promoted", False)),
            promotion_reason=str(result.get("promotion_reason")) if result.get("promotion_reason") else None,
            training_time_seconds=float(result.get("training_time_seconds", 0.0)),
            metrics={k: float(v) for k, v in dict(result.get("metrics", {})).items()},
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.time() - started) * 1000)
        observe_ms("jobs.retrain_ml.duration_ms", duration_ms)
        inc_counter("jobs.retrain_ml.count", 1)
        log_event(
            "jobs.retrain_ml",
            {
                "project_id": auth.project_id,
                "status": "error",
                "job_run_id": job_run_id,
                "error": str(exc),
            },
        )
        return JobRetrainMLResponse(
            status="error",
            job_run_id=job_run_id,
            model_version=None,
            training_time_seconds=None,
            metrics={},
            error=str(exc),
        )
    finally:
        container.job_lock.release(lock_key)


@router.post("/v1/jobs/retrain-ml-if-needed", response_model=JobRetrainMLResponse)
def retrain_ml_if_needed(
    req: JobRetrainMLRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> JobRetrainMLResponse:
    if container.ml_facade is None:
        return JobRetrainMLResponse(
            status="ml_unavailable",
            job_run_id="",
            model_version=None,
            active_version=None,
            promoted=None,
            promotion_reason=None,
            training_time_seconds=None,
            metrics={},
            error="ML facade no inicializado",
        )

    lock_key = container.settings.ml_retrain_lock_key
    if not container.job_lock.try_lock(lock_key):
        return JobRetrainMLResponse(
            status="locked",
            job_run_id="",
            model_version=None,
            active_version=None,
            promoted=None,
            promotion_reason=None,
            training_time_seconds=None,
            metrics={},
            error=None,
        )

    started = time.time()
    job_run_id = str(uuid.uuid4())
    try:
        result = container.ml_facade.retrain_if_needed(
            min_hours=int(getattr(container.settings, "ml_auto_retrain_min_hours", 24)),
            version=req.version if req else None,
            hyperparameters=req.hyperparameters if req else None,
            auto_promote=req.auto_promote if req else bool(getattr(container.settings, "ml_auto_promote", True)),
        )
        duration_ms = int((time.time() - started) * 1000)
        observe_ms("jobs.retrain_ml_if_needed.duration_ms", duration_ms)
        inc_counter("jobs.retrain_ml_if_needed.count", 1)
        log_event(
            "jobs.retrain_ml_if_needed",
            {
                "project_id": auth.project_id,
                "status": str(result.get("status", "ok")),
                "job_run_id": job_run_id,
                "active_version": result.get("active_version"),
                "reason": result.get("reason"),
            },
        )
        return JobRetrainMLResponse(
            status=str(result.get("status", "ok")),
            job_run_id=job_run_id,
            model_version=str(result.get("model_version")) if result.get("model_version") else None,
            active_version=str(result.get("active_version")) if result.get("active_version") else None,
            promoted=bool(result.get("promoted")) if result.get("promoted") is not None else None,
            promotion_reason=str(result.get("promotion_reason") or result.get("reason") or ""),
            training_time_seconds=(
                float(result.get("training_time_seconds"))
                if result.get("training_time_seconds") is not None
                else None
            ),
            metrics={k: float(v) for k, v in dict(result.get("metrics", {})).items()},
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = int((time.time() - started) * 1000)
        observe_ms("jobs.retrain_ml_if_needed.duration_ms", duration_ms)
        inc_counter("jobs.retrain_ml_if_needed.count", 1)
        log_event(
            "jobs.retrain_ml_if_needed",
            {
                "project_id": auth.project_id,
                "status": "error",
                "job_run_id": job_run_id,
                "error": str(exc),
            },
        )
        return JobRetrainMLResponse(
            status="error",
            job_run_id=job_run_id,
            model_version=None,
            active_version=None,
            promoted=None,
            promotion_reason=None,
            training_time_seconds=None,
            metrics={},
            error=str(exc),
        )
    finally:
        container.job_lock.release(lock_key)
