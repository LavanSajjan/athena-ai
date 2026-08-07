"""Tests for provider-independent tabular dataset profiling."""

from dataclasses import FrozenInstanceError

import polars as pl
import pytest

from packages.loaders.models import TabularLoadResult
from packages.models.domain.storage import StorageAsset
from packages.profiling.models import ProfileResult
from packages.profiling.profiler import DatasetProfiler


def _load_result(dataframe: pl.DataFrame) -> TabularLoadResult:
    """Build a loaded-table result without creating or reading a filesystem asset."""
    return TabularLoadResult(
        asset=StorageAsset(
            reference="memory/sales.csv",
            name="sales",
            extension="csv",
            uri="memory://sales.csv",
            size_bytes=128,
            sha256="a" * 64,
        ),
        dataframe=dataframe,
        row_count=dataframe.height,
        column_count=dataframe.width,
        column_names=dataframe.columns,
        estimated_size_bytes=dataframe.estimated_size(),
    )


def test_profile_returns_dataset_column_and_quality_summaries() -> None:
    """The profiler should describe tabular content and source metadata."""
    dataframe = pl.DataFrame(
        {
            "customer_id": [1, 2, 2, 3],
            "segment": ["enterprise", "small", "small", None],
            "revenue": [10.5, 20.0, 20.0, 30.0],
            "created_at": ["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03"],
            "empty": [None, None, None, None],
        },
        schema={
            "customer_id": pl.Int64,
            "segment": pl.String,
            "revenue": pl.Float64,
            "created_at": pl.Date,
            "empty": pl.String,
        },
    )

    profile = DatasetProfiler().profile(_load_result(dataframe))

    assert isinstance(profile, ProfileResult)
    assert profile.summary.reference == "memory/sales.csv"
    assert profile.summary.name == "sales"
    assert profile.summary.row_count == 4
    assert profile.summary.column_count == 5
    assert profile.columns[1].name == "segment"
    assert profile.columns[1].null_count == 1
    assert profile.columns[1].null_percentage == 25.0
    assert profile.columns[1].distinct_count == 2
    assert profile.columns[1].distinct_percentage == 50.0
    assert profile.data_quality.total_cell_count == 20
    assert profile.data_quality.null_cell_count == 5
    assert profile.data_quality.null_percentage == 25.0
    assert profile.data_quality.duplicate_row_count == 1
    assert profile.data_quality.duplicate_row_percentage == 25.0
    assert profile.data_quality.empty_column_count == 1


def test_profile_recommends_keys_identifiers_categories_measures_and_dates() -> None:
    """The profiler should apply deterministic recommendation heuristics."""
    dataframe = pl.DataFrame(
        {
            "order_id": [101, 102, 103, 104, 105],
            "status": ["new", "paid", "paid", "new", "paid"],
            "amount": [12.5, 9.0, 22.0, 5.0, 10.0],
            "ordered_on": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
        },
        schema={
            "order_id": pl.Int64,
            "status": pl.String,
            "amount": pl.Float64,
            "ordered_on": pl.Date,
        },
    )

    recommendations = DatasetProfiler().profile(_load_result(dataframe)).recommendations

    assert recommendations.potential_primary_keys == ("order_id",)
    assert recommendations.identifier_columns == ("order_id",)
    assert recommendations.categorical_columns == ("status",)
    assert recommendations.numeric_measures == ("amount",)
    assert recommendations.date_dimensions == ("ordered_on",)


def test_profile_handles_empty_dataframes_without_division_errors() -> None:
    """Empty datasets should have zero-valued quality metrics and recommendations."""
    dataframe = pl.DataFrame(
        schema={"record_id": pl.Int64, "category": pl.String, "event_date": pl.Date}
    )

    profile = DatasetProfiler().profile(_load_result(dataframe))

    assert profile.summary.row_count == 0
    assert [column.null_percentage for column in profile.columns] == [0.0, 0.0, 0.0]
    assert profile.data_quality.total_cell_count == 0
    assert profile.data_quality.null_percentage == 0.0
    assert profile.data_quality.duplicate_row_count == 0
    assert profile.data_quality.empty_column_count == 0
    assert profile.recommendations.potential_primary_keys == ()
    assert profile.recommendations.identifier_columns == ()
    assert profile.recommendations.categorical_columns == ()
    assert profile.recommendations.categorical_columns == ()
    assert profile.recommendations.numeric_measures == ()
    assert profile.recommendations.date_dimensions == ()


def test_profile_models_are_immutable() -> None:
    """Profile results should not allow mutation after computation."""
    profile = DatasetProfiler().profile(_load_result(pl.DataFrame({"id": [1]})))

    with pytest.raises(FrozenInstanceError):
        profile.summary.row_count = 2  # type: ignore[misc]
