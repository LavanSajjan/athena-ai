"""In-memory DuckDB implementation of the tabular query port."""

from dataclasses import dataclass, field
from threading import Lock, Timer
from time import perf_counter

import duckdb

from packages.interfaces.query import QueryEngine
from packages.loaders.models import TabularLoadResult
from packages.query.models import QueryResult
from packages.shared.exceptions import (
    QueryExecutionError,
    QueryResourceLimitError,
)


@dataclass
class _QueryExecutionState:
    completed: bool = False
    timed_out: bool = False
    lock: Lock = field(default_factory=Lock)


class DuckDBQueryEngine(QueryEngine):
    """Execute SQL against a Polars DataFrame registered as ``dataset``."""

    def __init__(
        self,
        memory_limit: str = "512MB",
        timeout_seconds: float = 30.0,
    ) -> None:
        """Configure DuckDB execution limits for one application-scoped engine."""
        self.memory_limit = memory_limit
        self.timeout_seconds = timeout_seconds

    def execute(self, dataset: TabularLoadResult, sql: str) -> QueryResult:
        """Execute ``sql`` using an isolated in-memory DuckDB connection."""
        if not sql.strip():
            raise QueryExecutionError("SQL text must not be empty.")

        state = _QueryExecutionState()
        try:
            with duckdb.connect(
                database=":memory:",
                config={
                    "enable_external_access": "false",
                    "memory_limit": self.memory_limit,
                },
            ) as connection:
                connection.register("dataset", dataset.dataframe)
                timeout = Timer(
                    self.timeout_seconds,
                    self._interrupt_for_timeout,
                    args=(connection, state),
                )
                timeout.start()
                try:
                    started_at = perf_counter()
                    dataframe = connection.execute(sql).pl()
                    execution_time_ms = (perf_counter() - started_at) * 1000
                    with state.lock:
                        state.completed = True
                finally:
                    timeout.cancel()
        except duckdb.Error as error:
            with state.lock:
                timed_out = state.timed_out
            if timed_out:
                raise QueryResourceLimitError(
                    "Query execution exceeded the configured timeout."
                ) from error
            raise QueryExecutionError("Unable to execute SQL against dataset.") from error

        with state.lock:
            timed_out = state.timed_out

        if timed_out:
            raise QueryResourceLimitError("Query execution exceeded the configured timeout.")

        return QueryResult(
            sql=sql,
            dataframe=dataframe,
            row_count=dataframe.height,
            column_count=dataframe.width,
            execution_time_ms=execution_time_ms,
        )

    def _interrupt_for_timeout(
        self,
        connection: duckdb.DuckDBPyConnection,
        state: _QueryExecutionState,
    ) -> None:
        """Interrupt a running DuckDB query once its execution deadline elapses."""
        with state.lock:
            if state.completed:
                return
            state.timed_out = True

        connection.interrupt()
