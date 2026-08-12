"""Tests for the provider-independent in-memory DuckDB query engine."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import duckdb
import polars as pl
import pytest

from packages.config.settings import Settings
from packages.interfaces.query import QueryEngine
from packages.loaders.models import TabularLoadResult
from packages.models.domain.storage import StorageAsset
from packages.query.duckdb import DuckDBQueryEngine
from packages.query.models import QueryResult
from packages.shared.exceptions import (
    QueryExecutionError,
    QueryResourceLimitError,
)


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


def test_engine_passes_memory_and_external_access_limits_to_duckdb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter must configure DuckDB's execution boundary at connection creation."""
    captured: dict[str, object] = {}

    class Relation:
        def pl(self) -> pl.DataFrame:
            return pl.DataFrame({"id": [1]})

    class Connection:
        def __enter__(self) -> "Connection":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def register(self, _: str, __: pl.DataFrame) -> None:
            return None

        def execute(self, _: str) -> Relation:
            return Relation()

        def interrupt(self) -> None:
            return None

    def connect(*, database: str, config: dict[str, str]) -> Connection:
        captured["database"] = database
        captured["config"] = config
        return Connection()

    monkeypatch.setattr("packages.query.duckdb.duckdb.connect", connect)

    DuckDBQueryEngine(memory_limit="64MB").execute(
        _dataset(pl.DataFrame({"id": [1]})),
        "SELECT * FROM dataset",
    )

    assert captured == {
        "database": ":memory:",
        "config": {"enable_external_access": "false", "memory_limit": "64MB"},
    }


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


def test_execute_wraps_timeout_as_resource_limit_error() -> None:
    """The watchdog must interrupt a query and expose a typed Athena exception."""
    with pytest.raises(QueryResourceLimitError) as error:
        DuckDBQueryEngine(timeout_seconds=0.01).execute(
            _dataset(pl.DataFrame({"id": [1]})),
            "SELECT SUM(a.range * b.range) "
            "FROM range(1000000) a CROSS JOIN range(1000000) b",
        )

    assert isinstance(error.value.__cause__, duckdb.Error)


def test_query_governance_settings_defaults_and_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resource governance settings should have safe defaults and standard env overrides."""
    monkeypatch.delenv("DATASET_QUERY_MEMORY_LIMIT", raising=False)
    monkeypatch.delenv("DATASET_QUERY_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DATASET_QUERY_MAX_ROWS", raising=False)
    defaults = Settings()
    monkeypatch.setenv("DATASET_QUERY_MEMORY_LIMIT", "64MB")
    monkeypatch.setenv("DATASET_QUERY_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("DATASET_QUERY_MAX_ROWS", "25")
    overridden = Settings()

    assert (
        defaults.dataset_query_memory_limit,
        defaults.dataset_query_timeout_seconds,
        defaults.dataset_query_max_rows,
    ) == ("512MB", 30.0, 10_000)
    assert (
        overridden.dataset_query_memory_limit,
        overridden.dataset_query_timeout_seconds,
        overridden.dataset_query_max_rows,
    ) == ("64MB", 1.5, 25)


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


def test_execute_does_not_timeout_after_successful_completion() -> None:
    """A fast query that completes should return successfully without being interrupted."""
    dataset = _dataset(pl.DataFrame({"id": [1, 2, 3]}))

    result = DuckDBQueryEngine(timeout_seconds=1.0).execute(
        dataset,
        "SELECT * FROM dataset",
    )

    assert result.row_count == 3
