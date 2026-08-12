"""Application orchestration for profiling registered datasets."""

from uuid import UUID

from packages.domains.dataset.models import Dataset
from packages.domains.dataset.service import DatasetService
from packages.interfaces.storage import StorageProvider
from packages.loaders.csv import CSVLoader
from packages.loaders.excel import ExcelLoader
from packages.loaders.models import TabularLoadResult
from packages.profiling.models import ProfileResult
from packages.profiling.profiler import DatasetProfiler
from packages.shared.exceptions import UnsupportedDatasetFormatError


class DatasetProfilingService:
    """Load and profile a registered dataset using its retained reference."""

    def __init__(
        self,
        dataset_service: DatasetService,
        storage_provider: StorageProvider,
        profiler: DatasetProfiler | None = None,
    ) -> None:
        self.dataset_service = dataset_service
        self.storage_provider = storage_provider
        self.profiler = profiler or DatasetProfiler()

    def profile(self, dataset_id: UUID) -> ProfileResult:
        """Load and profile the dataset identified by ``dataset_id``."""
        dataset = self.dataset_service.get(dataset_id)
        result = self._load(dataset)
        return self.profiler.profile(result)

    def _load(self, dataset: Dataset) -> TabularLoadResult:
        """Load a dataset with the supported loader for its source type."""
        if dataset.source_type == "csv":
            return CSVLoader(self.storage_provider).load(dataset.reference)
        if dataset.source_type in {"xls", "xlsx"}:
            return ExcelLoader(self.storage_provider).load(dataset.reference)
        raise UnsupportedDatasetFormatError(
            f"Unsupported dataset format: {dataset.source_type}"
        )
