from uuid import UUID

from packages.domains.dataset.models import Dataset


class DatasetRegistry:
    """In-memory dataset registry."""

    def __init__(self) -> None:
        self._datasets: dict[UUID, Dataset] = {}

    def register(self, dataset: Dataset) -> None:
        self._datasets[dataset.id] = dataset

    def get(self, dataset_id: UUID) -> Dataset | None:
        return self._datasets.get(dataset_id)

    def list(self) -> list[Dataset]:
        return list(self._datasets.values())