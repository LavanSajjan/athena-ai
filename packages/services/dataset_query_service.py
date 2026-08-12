"""Application orchestration for querying registered datasets."""

from uuid import UUID

from packages.domains.dataset.models import Dataset
from packages.domains.dataset.service import DatasetService
from packages.interfaces.query import QueryEngine
from packages.interfaces.storage import StorageProvider
from packages.loaders.csv import CSVLoader
from packages.loaders.excel import ExcelLoader
from packages.loaders.models import TabularLoadResult
from packages.query.duckdb import DuckDBQueryEngine
from packages.query.models import QueryResult
from packages.shared.exceptions import QueryExecutionError, UnsupportedDatasetFormatError


class DatasetQueryService:
    """Load and query a registered dataset using its retained reference."""

    def __init__(
        self,
        dataset_service: DatasetService,
        storage_provider: StorageProvider,
        query_engine: QueryEngine | None = None,
    ) -> None:
        self.dataset_service = dataset_service
        self.storage_provider = storage_provider
        self.query_engine = query_engine or DuckDBQueryEngine()

    def query(self, dataset_id: UUID, sql: str) -> QueryResult:
        """Load the dataset identified by ``dataset_id`` and execute ``sql``."""
        self._validate_sql(sql)
        dataset = self.dataset_service.get(dataset_id)
        return self.query_engine.execute(self._load(dataset), sql)

    def _load(self, dataset: Dataset) -> TabularLoadResult:
        """Load a dataset with the supported loader for its source type."""
        if dataset.source_type == "csv":
            return CSVLoader(self.storage_provider).load(dataset.reference)
        if dataset.source_type in {"xls", "xlsx"}:
            return ExcelLoader(self.storage_provider).load(dataset.reference)
        raise UnsupportedDatasetFormatError(
            f"Unsupported dataset format: {dataset.source_type}"
        )

    def _validate_sql(self, sql: str) -> None:
        """Apply the narrow read-only policy used by the public query endpoint."""
        normalized_sql = sql.strip()
        if not normalized_sql:
            raise QueryExecutionError("SQL text must not be empty.")
        if ";" in normalized_sql:
            raise QueryExecutionError("SQL text must contain exactly one statement.")
        if not normalized_sql.upper().startswith("SELECT"):
            raise QueryExecutionError("Only SELECT-leading SQL statements are supported.")
