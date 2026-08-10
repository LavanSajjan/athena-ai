"""API models for dataset endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from packages.domains.dataset.enums import DatasetStatus


class DatasetRegistrationRequest(BaseModel):
    """Request payload used to register a dataset asset."""

    reference: str


class DatasetResponse(BaseModel):
    """Response model representing a registered dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    asset_uri: str
    size_bytes: int
    created_at: datetime
    status: DatasetStatus
    sha256: str | None
    extension: str
