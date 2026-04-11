import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.config import Settings
from src.db.session import check_db_health
from src.observability.metrics import snapshot


router = APIRouter()


class HealthStatusResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    service: str
    version: str
    git_sha: str = ""
    build_time: str = ""
    api_version: str = "v1"


class MetricsSnapshotResponse(BaseModel):
    counters: dict[str, float] = Field(default_factory=dict)
    timers: dict[str, dict[str, float]] = Field(default_factory=dict)


def _get_settings(request) -> Settings:
    return request.app.state.settings


@router.get("/healthz", response_model=HealthStatusResponse)
def healthz() -> HealthStatusResponse:
    return HealthStatusResponse(status="ok")


@router.get("/readyz", response_model=HealthStatusResponse)
def readyz(request=Depends(lambda r: r)) -> HealthStatusResponse:
    settings: Settings = request.app.state.settings
    if not check_db_health(settings):
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


@router.get("/v1/version", response_model=VersionResponse)
def version() -> VersionResponse:
    return VersionResponse(
        service=os.getenv("SERVICE_NAME", "ponti-ai"),
        version=os.getenv("SERVICE_VERSION", ""),
        git_sha=os.getenv("SERVICE_GIT_SHA", ""),
        build_time=os.getenv("SERVICE_BUILD_TIME", ""),
        api_version="v1",
    )


@router.get("/v1/healthz", response_model=HealthStatusResponse)
def healthz_v1() -> HealthStatusResponse:
    return HealthStatusResponse(status="ok")


@router.get("/v1/readyz", response_model=HealthStatusResponse)
def readyz_v1(request=Depends(lambda r: r)) -> HealthStatusResponse:
    settings: Settings = request.app.state.settings
    if not check_db_health(settings):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="DB no disponible")
    return HealthStatusResponse(status="ok")
