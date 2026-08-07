"""Vectorized, provider-independent profiling for tabular datasets."""

import polars as pl

from packages.loaders.models import TabularLoadResult
from packages.profiling.models import (
    ColumnProfile,
    DataQualityProfile,
    DatasetSummary,
    ProfileRecommendations,
    ProfileResult,
)


class DatasetProfiler:
    """Produce descriptive profiles from loaded tabular data."""

    _IDENTIFIER_SUFFIXES = ("_id", "_key", "_code", "_uuid")
    _IDENTIFIER_NAMES = {"id", "key", "uuid", "identifier", "code"}
    _CATEGORICAL_CARDINALITY_LIMIT = 50
    _CATEGORICAL_CARDINALITY_RATIO = 0.5

    def profile(self, result: TabularLoadResult) -> ProfileResult:
        """Profile a loaded table without accessing its storage provider."""
        dataframe = result.dataframe
        row_count = dataframe.height
        column_profiles = self._profile_columns(dataframe)

        return ProfileResult(
            summary=DatasetSummary(
                reference=result.asset.reference,
                name=result.asset.name,
                row_count=row_count,
                column_count=dataframe.width,
                estimated_size_bytes=result.estimated_size_bytes,
            ),
            columns=column_profiles,
            data_quality=self._profile_data_quality(dataframe, column_profiles),
            recommendations=self._recommend(dataframe, column_profiles),
        )

    def _profile_columns(self, dataframe: pl.DataFrame) -> tuple[ColumnProfile, ...]:
        """Compute null and distinct metrics for every column in one Polars query."""
        expressions: list[pl.Expr] = []

        for index, name in enumerate(dataframe.columns):
            expressions.extend(
                (
                    pl.col(name).null_count().alias(f"null_count_{index}"),
                    pl.col(name).drop_nulls().n_unique().alias(f"distinct_count_{index}"),
                )
            )

        statistics = dataframe.select(expressions) if expressions else pl.DataFrame()
        row_count = dataframe.height

        return tuple(
            ColumnProfile(
                name=name,
                data_type=str(dataframe.schema[name]),
                null_count=self._statistic(statistics, f"null_count_{index}"),
                null_percentage=self._percentage(
                    self._statistic(statistics, f"null_count_{index}"), row_count
                ),
                distinct_count=self._statistic(statistics, f"distinct_count_{index}"),
                distinct_percentage=self._percentage(
                    self._statistic(statistics, f"distinct_count_{index}"), row_count
                ),
            )
            for index, name in enumerate(dataframe.columns)
        )

    def _profile_data_quality(
        self,
        dataframe: pl.DataFrame,
        columns: tuple[ColumnProfile, ...],
    ) -> DataQualityProfile:
        """Compute dataset-level quality metrics from vectorized operations."""
        row_count = dataframe.height
        total_cell_count = row_count * dataframe.width
        null_cell_count = sum(column.null_count for column in columns)
        duplicate_row_count = row_count - dataframe.unique().height
        empty_column_count = sum(
            column.null_count == row_count for column in columns
        ) if row_count else 0

        return DataQualityProfile(
            total_cell_count=total_cell_count,
            null_cell_count=null_cell_count,
            null_percentage=self._percentage(null_cell_count, total_cell_count),
            duplicate_row_count=duplicate_row_count,
            duplicate_row_percentage=self._percentage(duplicate_row_count, row_count),
            empty_column_count=empty_column_count,
        )

    def _recommend(
        self,
        dataframe: pl.DataFrame,
        columns: tuple[ColumnProfile, ...],
    ) -> ProfileRecommendations:
        """Classify columns with deterministic type and cardinality heuristics."""
        row_count = dataframe.height
        if not row_count:
            return ProfileRecommendations((), (), (), (), ())

        primary_keys = tuple(
            column.name
            for column in columns
            if column.null_count == 0
            and column.distinct_count == row_count
            and (
                self._is_identifier_name(column.name)
                or self._is_integer(dataframe.schema[column.name])
            )
        )
        identifiers = tuple(
            column.name
            for column in columns
            if self._is_identifier_name(column.name)
            and column.null_count == 0
            and column.distinct_count == row_count
        )
        categorical_limit = min(
            self._CATEGORICAL_CARDINALITY_LIMIT,
            max(1, int(row_count * self._CATEGORICAL_CARDINALITY_RATIO)),
        )
        categorical = tuple(
            column.name
            for column in columns
            if self._is_string(dataframe.schema[column.name])
            and column.distinct_count <= categorical_limit
        )
        numeric_measures = tuple(
            column.name
            for column in columns
            if dataframe.schema[column.name].is_numeric()
            and column.name not in primary_keys
            and column.name not in identifiers
        )
        date_dimensions = tuple(
            column.name
            for column in columns
            if self._is_date_dimension(dataframe.schema[column.name])
        )

        return ProfileRecommendations(
            potential_primary_keys=primary_keys,
            identifier_columns=identifiers,
            categorical_columns=categorical,
            numeric_measures=numeric_measures,
            date_dimensions=date_dimensions,
        )

    def _statistic(self, statistics: pl.DataFrame, name: str) -> int:
        """Return one non-null integer computed by a Polars aggregation."""
        return int(statistics.get_column(name)[0])

    def _percentage(self, numerator: int, denominator: int) -> float:
        """Return a percentage without division errors for empty datasets."""
        return (numerator / denominator * 100) if denominator else 0.0

    def _is_identifier_name(self, name: str) -> bool:
        """Recognize conventional identifier column names."""
        normalized = name.strip().lower()
        return (
            normalized in self._IDENTIFIER_NAMES
            or normalized.endswith(self._IDENTIFIER_SUFFIXES)
        )

    def _is_integer(self, data_type: pl.DataType) -> bool:
        """Return whether a Polars data type represents an integer surrogate key."""
        return str(data_type).startswith(("Int", "UInt"))

    def _is_string(self, data_type: pl.DataType) -> bool:
        """Return whether a Polars data type represents textual categorical values."""
        return str(data_type) in {"String", "Categorical", "Enum"}

    def _is_date_dimension(self, data_type: pl.DataType) -> bool:
        """Return whether a Polars data type represents a date or timestamp."""
        return str(data_type).startswith(("Date", "Datetime"))
