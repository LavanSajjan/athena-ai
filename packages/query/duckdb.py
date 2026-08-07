"""In-memory DuckDB implementation of the tabular query port."""

from time import perf_counter

import duckdb

from packages.interfaces.query import QueryEngine
from packages.loaders.models import TabularLoadResult
from packages.query.models import QueryResult
from packages.shared.exceptions import QueryExecutionError


class DuckDBQueryEngine(QueryEngine):
    """Execute SQL against a Polars DataFrame registered as ``dataset``."""

    def execute(self, dataset: TabularLoadResult, sql: str) -> QueryResult:
        """Execute ``sql`` using an isolated in-memory DuckDB connection."""
        if not sql.strip():
            raise QueryExecutionError("SQL text must not be empty.")

        try:
            with duckdb.connect(database=":memory:") as connection:
                connection.register("dataset", dataset.dataframe)
                started_at = perf_counter()
                dataframe = connection.execute(sql).pl()
                execution_time_ms = (perf_counter() - started_at) * 1000
        except duckdb.Error as error:
            raise QueryExecutionError("Unable to execute SQL against dataset.") from error

        return QueryResult(
            sql=sql,
            dataframe=dataframe,
            row_count=dataframe.height,
            column_count=dataframe.width,
            execution_time_ms=execution_time_ms,
        )
