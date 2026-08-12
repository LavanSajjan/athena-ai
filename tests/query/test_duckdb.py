"""Tests for the provider-independent in-memory DuckDB query engine."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import duckdb
import polars as pl
import pytest

from packages.interfaces.query import QueryEngine
from packages.loaders.models import TabularLoadResult
from packages.models.domain.storage import StorageAsset
from packages.query.duckdb import DuckDBQueryEngine
from packages.query.models import QueryResult
from packages.shared.exceptions import QueryExecutionError


def _dataset(dataframe: pl.DataFrame) -> TabularLoadResult:
    """Construct a loaded dataset backed entirely by in-memory values."""
    return TabularLoadResult(
        asset=StorageAsset(
            reference="memory/orders.csv",
            name="orders",
            extension="csv",
            uri="memory://orders.csv",
            size_bytes=128,
            sha256="a" * 64,
        ),
        dataframe=dataframe,
        row_count=dataframe.height,
        column_count=dataframe.width,
        column_names=dataframe.columns,
        estimated_size_bytes=int(dataframe.estimated_size()),
    )


def test_engine_implements_query_protocol() -> None:
    """The DuckDB adapter should conform to the query engine port."""
    assert isinstance(DuckDBQueryEngine(), QueryEngine)


def test_execute_registers_dataset_and_returns_polars_result() -> None:
    """Queries should use the required dataset relation and return a Polars frame."""
    dataset = _dataset(
        pl.DataFrame(
            {
                "region": ["west", "east", "west"],
                "amount": [12, 8, 20],
            }
        )
    )
    sql = "SELECT region, SUM(amount) AS revenue FROM dataset GROUP BY region ORDER BY region"

    result = DuckDBQueryEngine().execute(dataset, sql)

    assert isinstance(result, QueryResult)
    assert isinstance(result.dataframe, pl.DataFrame)
    assert result.sql == sql
    assert result.dataframe.to_dicts() == [
        {"region": "east", "revenue": 8},
        {"region": "west", "revenue": 32},
    ]
    assert result.row_count == 2
    assert result.column_count == 2
    assert result.execution_time_ms >= 0


def test_execute_supports_filtering_and_empty_results() -> None:
    """SQL filtering should produce a correctly typed empty Polars DataFrame."""
    dataset = _dataset(pl.DataFrame({"id": [1, 2], "amount": [10, 20]}))

    result = DuckDBQueryEngine().execute(
        dataset,
        "SELECT id, amount FROM dataset WHERE amount > 100",
    )

    assert result.dataframe.schema == {"id": pl.Int64, "amount": pl.Int64}
    assert result.dataframe.is_empty()
    assert result.row_count == 0
    assert result.column_count == 2


@pytest.mark.parametrize("sql", ["SELECT missing FROM dataset", "SELEC * FROM dataset"])
def test_execute_wraps_duckdb_errors(sql: str) -> None:
    """DuckDB failures should become typed query exceptions with their cause retained."""
    dataset = _dataset(pl.DataFrame({"id": [1]}))

    with pytest.raises(QueryExecutionError) as error:
        DuckDBQueryEngine().execute(dataset, sql)

    assert isinstance(error.value.__cause__, duckdb.Error)


def test_execute_rejects_external_resource_access(tmp_path: Path) -> None:
    """External DuckDB table functions must not bypass the loaded dataset boundary."""
    resource_path = tmp_path / "external.csv"
    resource_path.write_text("id\n99\n", encoding="utf-8")
    dataset = _dataset(pl.DataFrame({"id": [1]}))

    with pytest.raises(QueryExecutionError) as error:
        DuckDBQueryEngine().execute(
            dataset,
            f"SELECT * FROM read_csv_auto('{resource_path.as_posix()}')",
        )

    assert isinstance(error.value.__cause__, duckdb.Error)


def test_execute_rejects_empty_sql_before_creating_a_connection() -> None:
    """Blank SQL should fail with the query engine's typed exception."""
    dataset = _dataset(pl.DataFrame({"id": [1]}))

    with pytest.raises(QueryExecutionError, match="must not be empty"):
        DuckDBQueryEngine().execute(dataset, "  \n")


def test_query_result_is_immutable() -> None:
    """Query execution metadata should not be mutable after execution."""
    dataset = _dataset(pl.DataFrame({"id": [1]}))

    result = DuckDBQueryEngine().execute(dataset, "SELECT * FROM dataset")

    with pytest.raises(FrozenInstanceError):
        result.row_count = 2  # type: ignore[misc]
