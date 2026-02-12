from fastapi import APIRouter, Depends, HTTPException, status

from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.inbound.api.schemas.insights import HealthStatusResponse, MetricsSnapshotResponse
from adapters.outbound.db.session import check_db_health
from adapters.outbound.observability.metrics import snapshot

router = APIRouter()


@router.get("/healthz", response_model=HealthStatusResponse)
def healthz() -> HealthStatusResponse:
    return HealthStatusResponse(status="ok")


@router.get("/readyz", response_model=HealthStatusResponse)
def readyz(container: AppContainer = Depends(get_container)) -> HealthStatusResponse:
    if not check_db_health(container.settings):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DB no disponible")
    return HealthStatusResponse(status="ok")


@router.get("/metrics", response_model=MetricsSnapshotResponse)
def metrics() -> MetricsSnapshotResponse:
    raw = snapshot()
    return MetricsSnapshotResponse(
        counters={str(k): float(v) for k, v in dict(raw.get("counters", {})).items()},
        timers={
            str(k): {str(metric): float(value) for metric, value in dict(v).items()}
            for k, v in dict(raw.get("timers", {})).items()
        },
    )
