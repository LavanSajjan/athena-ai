"""API models for dataset profiling endpoints."""

from pydantic import BaseModel, ConfigDict


class ProfileResponseModel(BaseModel):
    """Base model for API responses created from profiling dataclasses."""

    model_config = ConfigDict(from_attributes=True)


class DatasetSummaryResponse(ProfileResponseModel):
    """API representation of high-level dataset profile facts."""

    reference: str
    name: str
    row_count: int
    column_count: int
    estimated_size_bytes: int


class ColumnProfileResponse(ProfileResponseModel):
    """API representation of one profiled column."""

    name: str
    data_type: str
    null_count: int
    null_percentage: float
    distinct_count: int
    distinct_percentage: float


class DataQualityProfileResponse(ProfileResponseModel):
    """API representation of dataset-level quality measures."""

    total_cell_count: int
    null_cell_count: int
    null_percentage: float
    duplicate_row_count: int
    duplicate_row_percentage: float
    empty_column_count: int


class ProfileRecommendationsResponse(ProfileResponseModel):
    """API representation of profile recommendations."""

    potential_primary_keys: tuple[str, ...]
    identifier_columns: tuple[str, ...]
    categorical_columns: tuple[str, ...]
    numeric_measures: tuple[str, ...]
    date_dimensions: tuple[str, ...]


class ProfileResultResponse(ProfileResponseModel):
    """API representation of a complete dataset profile."""

    summary: DatasetSummaryResponse
    columns: tuple[ColumnProfileResponse, ...]
    data_quality: DataQualityProfileResponse
    recommendations: ProfileRecommendationsResponse
