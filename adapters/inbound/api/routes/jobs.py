import time

from fastapi import APIRouter, Depends

from adapters.inbound.api.auth.headers import AuthContext, require_headers
from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import JobRecomputeRequest
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
    container.recompute_active.handle(project_id=auth.project_id, batch_size=req.batch_size if req else None)
    duration_ms = int((time.time() - started) * 1000)
    observe_ms("jobs.recompute.duration_ms", duration_ms)
    inc_counter("jobs.recompute.count", 1)
    log_event(
        "jobs.recompute",
        {
            "project_id": auth.project_id,
            "status": "ok",
        },
    )
    return {"status": "ok"}
