"""FastAPI dependencies for dataset endpoints."""

from typing import cast

from fastapi import Request

from packages.domains.dataset.service import DatasetService
from packages.services.dataset_profiling_service import DatasetProfilingService
from packages.services.dataset_query_service import DatasetQueryService


def get_dataset_service(request: Request) -> DatasetService:
    """Return the application-scoped dataset service for the current request."""
    return cast(DatasetService, request.app.state.dataset_service)


def get_dataset_profiling_service(request: Request) -> DatasetProfilingService:
    """Return the application-scoped dataset profiling service."""
    return cast(DatasetProfilingService, request.app.state.dataset_profiling_service)


def get_dataset_query_service(request: Request) -> DatasetQueryService:
    """Return the application-scoped dataset query service."""
    return cast(DatasetQueryService, request.app.state.dataset_query_service)
