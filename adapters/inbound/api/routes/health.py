from fastapi import APIRouter, Depends, HTTPException, status

from adapters.inbound.api.dependencies import AppContainer, get_container
from adapters.outbound.db.session import check_db_health
from adapters.outbound.observability.metrics import snapshot

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(container: AppContainer = Depends(get_container)) -> dict[str, str]:
    if not check_db_health(container.settings):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DB no disponible")
    return {"status": "ok"}


@router.get("/metrics")
def metrics() -> dict[str, dict[str, float]]:
    return snapshot()
