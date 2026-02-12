import time
import uuid

from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
    JobRetrainMLRequest,
    JobRetrainMLResponse,
    JobProcessQueueRequest,
    JobProcessQueueResponse,
    RecomputeEventRequest,
    RecomputeEventResponse,
    JobRecomputeBaselinesRequest,
    JobRecomputeBaselinesResponse,
    JobRecomputeRequest,
    JobRecomputeResponse,
)
from adapters.outbound.observability.logging import log_event
from adapters.outbound.observability.metrics import inc_counter, observe_ms

router = APIRouter()
HANDLED_JOB_ERRORS = (ValueError, RuntimeError, KeyError, OSError)


@router.post("/v1/jobs/recompute-queue/enqueue", response_model=RecomputeEventResponse)
def enqueue_recompute_event(
    req: RecomputeEventRequest,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> RecomputeEventResponse:
    debounce_seconds = (
        req.debounce_seconds
        if req.debounce_seconds is not None
        else container.settings.insights_recompute_debounce_seconds
    )
    result = container.queue_recompute_event.handle(
        project_id=auth.project_id,
        source=req.source,
        reason=req.reason,
        debounce_seconds=debounce_seconds,
    )
    return RecomputeEventResponse(status=result.status, project_id=result.project_id)


@router.post("/v1/jobs/recompute-queue/process", response_model=JobProcessQueueResponse)
def process_recompute_queue(
    req: JobProcessQueueRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> JobProcessQueueResponse:
    _ = auth
    limit = req.limit if req and req.limit else container.settings.insights_recompute_queue_batch_size
    workers = req.workers if req and req.workers else container.settings.insights_recompute_queue_workers
    result = container.process_recompute_queue.handle(
        limit=limit,
        workers=workers,
        lock_key_base=container.settings.insights_recompute_lock_key,
        stale_lock_seconds=container.settings.insights_recompute_stale_lock_seconds,
    )
    return JobProcessQueueResponse(
        status="ok",
        claimed=int(result.claimed),
        processed=int(result.processed),
        ok=int(result.ok),
        locked=int(result.locked),
        errors=int(result.errors),
    )


@router.post("/v1/jobs/recompute-active", response_model=JobRecomputeResponse)
def recompute_active(
    req: JobRecomputeRequest | None = None,
    auth: AuthContext = Depends(require_headers),
    container: AppContainer = Depends(get_container),
) -> JobRecomputeResponse:
    started = time.time()
    batch_size = req.batch_size if req else None
    result = container.recompute_active.handle(
        project_id=auth.project_id,
        lock_key=container.settings.insights_recompute_lock_key,
        batch_size=batch_size,
    )
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("jobs.recompute.duration_ms", duration_ms)
    inc_counter("jobs.recompute.count", 1)
    log_event(
        "jobs.recompute",
        {
            "project_id": auth.project_id,
            "status": result.status,
            "job_run_id": result.job_run_id,
            "batch_size": batch_size,
        },
    )
    return JobRecomputeResponse(status=result.status, job_run_id=result.job_run_id)


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
            "status": result.status,
            "job_run_id": result.job_run_id,
        },
    )
    return JobRecomputeBaselinesResponse(
        status=result.status,
        job_run_id=result.job_run_id,
        cohort_saved=int(result.cohort_saved),
        project_saved=int(result.project_saved),
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
    except HANDLED_JOB_ERRORS as exc:
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
    except HANDLED_JOB_ERRORS as exc:
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
