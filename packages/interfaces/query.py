"""Ports for executing SQL against loaded tabular datasets."""

from typing import Protocol, runtime_checkable

from packages.loaders.models import TabularLoadResult
from packages.query.models import QueryResult


@runtime_checkable
class QueryEngine(Protocol):
    """Executes SQL against one loaded tabular dataset."""

    def execute(self, dataset: TabularLoadResult, sql: str) -> QueryResult:
        """Execute SQL with the dataset registered under the name ``dataset``."""
