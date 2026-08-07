"""Immutable models produced by dataset profiling."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    """High-level facts about a profiled tabular dataset."""

    reference: str
    name: str
    row_count: int
    column_count: int
    estimated_size_bytes: int


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Profile information for one dataset column."""

    name: str
    data_type: str
    null_count: int
    null_percentage: float
    distinct_count: int
    distinct_percentage: float


@dataclass(frozen=True, slots=True)
class DataQualityProfile:
    """Dataset-level measures of completeness and duplication."""

    total_cell_count: int
    null_cell_count: int
    null_percentage: float
    duplicate_row_count: int
    duplicate_row_percentage: float
    empty_column_count: int


@dataclass(frozen=True, slots=True)
class ProfileRecommendations:
    """Heuristic recommendations inferred from column profiles."""

    potential_primary_keys: tuple[str, ...]
    identifier_columns: tuple[str, ...]
    categorical_columns: tuple[str, ...]
    numeric_measures: tuple[str, ...]
    date_dimensions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProfileResult:
    """Complete, immutable result of profiling one tabular dataset."""

    summary: DatasetSummary
    columns: tuple[ColumnProfile, ...]
    data_quality: DataQualityProfile
    recommendations: ProfileRecommendations
