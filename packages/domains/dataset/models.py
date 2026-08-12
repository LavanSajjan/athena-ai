from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from packages.domains.dataset.enums import DatasetStatus


class Dataset(BaseModel):
    """Represents a dataset known to Athena."""

    id: UUID = Field(default_factory=uuid4)

    name: str

    source_type: str

    reference: str

    asset_uri: str

    size_bytes: int

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    status: DatasetStatus = DatasetStatus.NEW

    sha256: str | None = None

    @property
    def extension(self) -> str:
        return Path(self.asset_uri).suffix.lower()
