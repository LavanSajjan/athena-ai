"""
API response models for system endpoints.
"""

from pydantic import BaseModel


class RootResponse(BaseModel):
    """Response model for the root endpoint."""

    name: str
    description: str
    version: str


class HealthResponse(BaseModel):
    """Response model for the health endpoint."""

    status: str


class VersionResponse(BaseModel):
    """Response model for the version endpoint."""

    version: str