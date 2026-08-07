from pathlib import Path

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.domains.dataset.registry import DatasetRegistry


class DatasetService:
    """Business logic for dataset registration."""

    def __init__(self, registry: DatasetRegistry | None = None):
        self.registry = registry or DatasetRegistry()

    def register(self, file_path: str) -> Dataset:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(file_path)

        dataset = Dataset(
            name=path.stem,
            source_type=path.suffix.replace(".", "").lower(),
            asset_uri=path.resolve().as_uri(),
            size_bytes=path.stat().st_size,
            status=DatasetStatus.REGISTERED,
        )

        self.registry.register(dataset)

        return dataset