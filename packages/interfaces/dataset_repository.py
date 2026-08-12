"""Port for durable Dataset lifecycle storage."""

from typing import Protocol
from uuid import UUID

from packages.domains.dataset.models import Dataset


class DatasetRepository(Protocol):
    """Store and retrieve Dataset aggregates without storage-provider semantics."""

    def initialize(self) -> None:
        """Initialize the repository and apply its schema migrations."""

    def close(self) -> None:
        """Release resources held by the repository."""

    def add(self, dataset: Dataset) -> None:
        """Persist a registered dataset."""

    def get(self, dataset_id: UUID) -> Dataset | None:
        """Return a dataset by identity, if it exists."""

    def list(self) -> list[Dataset]:
        """Return datasets in deterministic registration order."""
