from uuid import UUID

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.interfaces.dataset_repository import DatasetRepository
from packages.interfaces.storage import StorageProvider
from packages.shared.exceptions import DatasetNotFoundError


class DatasetService:
    """Business logic for registering and retrieving datasets."""

    def __init__(
        self,
        storage_provider: StorageProvider,
        repository: DatasetRepository,
        provider_id: str,
    ) -> None:
        """Initialize the service with storage and durable dataset dependencies."""
        self.storage_provider = storage_provider
        self.repository = repository
        self.provider_id = provider_id

    def register(self, reference: str) -> Dataset:
        """Register the asset identified by ``reference`` as a dataset."""
        asset = self.storage_provider.describe(reference)

        dataset = Dataset(
            provider_id=self.provider_id,
            name=asset.name,
            source_type=asset.extension,
            reference=asset.reference,
            asset_uri=asset.uri,
            size_bytes=asset.size_bytes,
            status=DatasetStatus.REGISTERED,
            sha256=asset.sha256,
        )

        self.repository.add(dataset)

        return dataset

    def get(self, dataset_id: UUID) -> Dataset:
        """Return the dataset with ``dataset_id`` or raise if it is unknown."""
        dataset = self.repository.get(dataset_id)

        if dataset is None:
            raise DatasetNotFoundError(str(dataset_id))

        return dataset

    def list(self) -> list[Dataset]:
        """Return every dataset registered by this service."""
        return self.repository.list()
