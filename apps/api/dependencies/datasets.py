"""FastAPI dependencies for dataset endpoints."""

from typing import cast

from fastapi import Request

from packages.domains.dataset.service import DatasetService
from packages.services.dataset_profiling_service import DatasetProfilingService


def get_dataset_service(request: Request) -> DatasetService:
    """Return the application-scoped dataset service for the current request."""
    return cast(DatasetService, request.app.state.dataset_service)


def get_dataset_profiling_service(request: Request) -> DatasetProfilingService:
    """Return the application-scoped dataset profiling service."""
    return cast(DatasetProfilingService, request.app.state.dataset_profiling_service)
