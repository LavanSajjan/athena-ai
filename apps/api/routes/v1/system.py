from fastapi import APIRouter

from packages.config.settings import get_settings
from packages.models.api.system import (
    HealthResponse,
    RootResponse,
    VersionResponse,
)

router = APIRouter(tags=["System"])

settings = get_settings()


@router.get("/", response_model=RootResponse)
async def root():
    return RootResponse(
        name=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy")


@router.get("/version", response_model=VersionResponse)
async def version():
    return VersionResponse(version=settings.app_version)