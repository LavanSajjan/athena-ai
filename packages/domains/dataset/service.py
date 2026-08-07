from uuid import UUID

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.domains.dataset.registry import DatasetRegistry
from packages.interfaces.storage import StorageProvider
from packages.shared.exceptions import DatasetNotFoundError


class DatasetService:
    """Business logic for registering and retrieving datasets."""

    def __init__(
        self,
        storage_provider: StorageProvider,
        registry: DatasetRegistry | None = None,
    ) -> None:
        """Initialize the service with a storage provider and dataset registry."""
        self.storage_provider = storage_provider
        self.registry = registry or DatasetRegistry()

    def register(self, reference: str) -> Dataset:
        """Register the asset identified by ``reference`` as a dataset."""
        asset = self.storage_provider.describe(reference)

        dataset = Dataset(
            name=asset.name,
            source_type=asset.extension,
            asset_uri=asset.uri,
            size_bytes=asset.size_bytes,
            status=DatasetStatus.REGISTERED,
            sha256=asset.sha256,
        )

        self.registry.register(dataset)

        return dataset

    def get(self, dataset_id: UUID) -> Dataset:
        """Return the dataset with ``dataset_id`` or raise if it is unknown."""
        dataset = self.registry.get(dataset_id)

        if dataset is None:
            raise DatasetNotFoundError(str(dataset_id))

        return dataset

    def list(self) -> list[Dataset]:
        """Return every dataset registered by this service."""
        return self.registry.list()
