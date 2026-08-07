"""Tests for the in-memory dataset registry."""

from packages.domains.dataset.models import Dataset
from packages.domains.dataset.registry import DatasetRegistry


def test_registry_returns_empty_list_initially() -> None:
    """The registry should contain no datasets before registration."""
    registry = DatasetRegistry()

    assert registry.list() == []


def test_registry_stores_and_retrieves_dataset() -> None:
    """The registry should retrieve a dataset using its generated identifier."""
    registry = DatasetRegistry()
    dataset = Dataset(
        name="sales",
        source_type="csv",
        asset_uri="file:///datasets/sales.csv",
        size_bytes=12,
    )

    registry.register(dataset)

    assert registry.get(dataset.id) == dataset
    assert registry.list() == [dataset]


def test_registry_returns_none_for_unknown_dataset() -> None:
    """The registry should return None when a dataset identifier is unknown."""
    registry = DatasetRegistry()
    dataset = Dataset(
        name="sales",
        source_type="csv",
        asset_uri="file:///datasets/sales.csv",
        size_bytes=12,
    )

    assert registry.get(dataset.id) is None
