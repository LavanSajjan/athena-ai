"""Immutable models produced by tabular query engines."""

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True, slots=True)
class QueryResult:
    """The materialized result and execution metadata for one SQL statement."""

    sql: str
    dataframe: pl.DataFrame
    row_count: int
    column_count: int
    execution_time_ms: float
