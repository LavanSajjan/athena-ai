"""FastAPI dependencies for dataset endpoints."""

from typing import cast

from fastapi import Request

from packages.domains.dataset.service import DatasetService


def get_dataset_service(request: Request) -> DatasetService:
    """Return the application-scoped dataset service for the current request."""
    return cast(DatasetService, request.app.state.dataset_service)
