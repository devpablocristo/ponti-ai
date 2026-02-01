import time

from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import (
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
