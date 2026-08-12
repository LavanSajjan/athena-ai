"""Version-one dataset API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.dependencies.datasets import (
    get_dataset_profiling_service,
    get_dataset_query_service,
    get_dataset_service,
)
from packages.domains.dataset.service import DatasetService
from packages.models.api.dataset import DatasetRegistrationRequest, DatasetResponse
from packages.models.api.profiling import ProfileResultResponse
from packages.models.api.query import DatasetQueryRequest, DatasetQueryResponse
from packages.services.dataset_profiling_service import DatasetProfilingService
from packages.services.dataset_query_service import DatasetQueryService
from packages.shared.constants import API_PREFIX
from packages.shared.exceptions import (
    CSVLoadError,
    DatasetNotFoundError,
    ExcelLoadError,
    InvalidStorageReferenceError,
    QueryExecutionError,
    StorageAssetNotFoundError,
    UnsupportedDatasetFormatError,
)

router = APIRouter(prefix=f"{API_PREFIX}/datasets", tags=["Datasets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def register_dataset(
    request: DatasetRegistrationRequest,
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    """Register a dataset asset through the application-scoped dataset service."""
    try:
        dataset = service.register(request.reference)
    except StorageAssetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidStorageReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return DatasetResponse.model_validate(dataset)


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> list[DatasetResponse]:
    """Return every dataset registered in the current application process."""
    return [DatasetResponse.model_validate(dataset) for dataset in service.list()]


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetResponse:
    """Return one registered dataset by its unique identifier."""
    try:
        dataset = service.get(dataset_id)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return DatasetResponse.model_validate(dataset)


@router.post("/{dataset_id}/profile", response_model=ProfileResultResponse)
async def profile_dataset(
    dataset_id: UUID,
    service: Annotated[DatasetProfilingService, Depends(get_dataset_profiling_service)],
) -> ProfileResultResponse:
    """Load and profile one registered dataset without persisting the result."""
    try:
        profile = service.profile(dataset_id)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except StorageAssetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidStorageReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except (CSVLoadError, ExcelLoadError, UnsupportedDatasetFormatError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return ProfileResultResponse.model_validate(profile)


@router.post("/{dataset_id}/query", response_model=DatasetQueryResponse)
async def query_dataset(
    dataset_id: UUID,
    request: DatasetQueryRequest,
    service: Annotated[DatasetQueryService, Depends(get_dataset_query_service)],
) -> DatasetQueryResponse:
    """Load and query one registered dataset without persisting the result."""
    try:
        result = service.query(dataset_id, request.sql)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except StorageAssetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except InvalidStorageReferenceError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except (
        CSVLoadError,
        ExcelLoadError,
        QueryExecutionError,
        UnsupportedDatasetFormatError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return DatasetQueryResponse(
        sql=result.sql,
        rows=result.dataframe.to_dicts(),
        row_count=result.row_count,
        column_count=result.column_count,
        execution_time_ms=result.execution_time_ms,
    )
