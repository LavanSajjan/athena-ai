"""Tests for dataset business logic independent of storage infrastructure."""

from io import BytesIO
from typing import BinaryIO
from uuid import uuid4

import pytest

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.domains.dataset.service import DatasetService
from packages.models.domain.storage import StorageAsset
from packages.shared.exceptions import DatasetNotFoundError, StorageAssetNotFoundError


class FakeStorageProvider:
    """Provide deterministic storage assets for dataset service tests."""

    def __init__(self, asset: StorageAsset) -> None:
        """Initialize the fake with the asset returned by ``describe``."""
        self.asset = asset
        self.references: list[str] = []

    def describe(self, reference: str) -> StorageAsset:
        """Record and return the configured storage asset."""
        self.references.append(reference)
        return self.asset

    def open_binary(self, reference: str) -> BinaryIO:
        """Return an empty binary stream for protocol compatibility."""
        return BytesIO()


class FakeDatasetRepository:
    """Keep datasets in memory for DatasetService unit tests."""

    def __init__(self) -> None:
        self.datasets: dict[object, Dataset] = {}

    def initialize(self) -> None:
        """Match the repository lifecycle contract."""

    def close(self) -> None:
        """Match the repository lifecycle contract."""

    def add(self, dataset: Dataset) -> None:
        """Store the dataset by its identity."""
        self.datasets[dataset.id] = dataset

    def get(self, dataset_id: object) -> Dataset | None:
        """Return the stored dataset, if present."""
        return self.datasets.get(dataset_id)

    def list(self) -> list[Dataset]:
        """Return inserted datasets."""
        return list(self.datasets.values())


def test_register_maps_storage_asset_to_dataset() -> None:
    """Registration should use metadata supplied by the storage provider."""
    asset = StorageAsset(
        reference="sample/sales.csv",
        name="sales",
        extension="csv",
        uri="file:///datasets/sample/sales.csv",
        size_bytes=24,
        sha256="a" * 64,
    )
    provider = FakeStorageProvider(asset)
    repository = FakeDatasetRepository()
    service = DatasetService(provider, repository, provider_id="local")

    dataset = service.register(asset.reference)

    assert provider.references == [asset.reference]
    assert dataset.name == asset.name
    assert dataset.provider_id == "local"
    assert dataset.source_type == asset.extension
    assert dataset.reference == asset.reference
    assert dataset.asset_uri == asset.uri
    assert dataset.size_bytes == asset.size_bytes
    assert dataset.sha256 == asset.sha256
    assert dataset.status is DatasetStatus.REGISTERED
    assert service.get(dataset.id) == dataset


def test_register_uses_injected_repository() -> None:
    """Registration should persist the created dataset in the supplied repository."""
    asset = StorageAsset(
        reference="sample/sales.csv",
        name="sales",
        extension="csv",
        uri="file:///datasets/sample/sales.csv",
        size_bytes=24,
        sha256="b" * 64,
    )
    repository = FakeDatasetRepository()
    service = DatasetService(FakeStorageProvider(asset), repository, provider_id="local")

    dataset = service.register(asset.reference)

    assert repository.get(dataset.id) == dataset
    assert service.list() == [dataset]


def test_register_propagates_storage_errors() -> None:
    """Registration should preserve an asset-not-found error from the provider."""
    asset = StorageAsset(
        reference="sample/sales.csv",
        name="sales",
        extension="csv",
        uri="file:///datasets/sample/sales.csv",
        size_bytes=24,
        sha256="c" * 64,
    )

    class MissingStorageProvider(FakeStorageProvider):
        """Represent a provider that cannot locate requested assets."""

        def describe(self, reference: str) -> StorageAsset:
            """Raise the expected missing-asset exception."""
            raise StorageAssetNotFoundError(reference)

    service = DatasetService(
        MissingStorageProvider(asset), FakeDatasetRepository(), provider_id="local"
    )

    with pytest.raises(StorageAssetNotFoundError):
        service.register(asset.reference)


def test_get_raises_for_unknown_dataset() -> None:
    """Retrieval should raise a typed error for an unknown dataset identifier."""
    asset = StorageAsset(
        reference="sample/sales.csv",
        name="sales",
        extension="csv",
        uri="file:///datasets/sample/sales.csv",
        size_bytes=24,
        sha256="d" * 64,
    )
    service = DatasetService(
        FakeStorageProvider(asset), FakeDatasetRepository(), provider_id="local"
    )

    with pytest.raises(DatasetNotFoundError):
        service.get(uuid4())
