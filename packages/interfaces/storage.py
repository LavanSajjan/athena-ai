"""Ports for accessing dataset assets from storage providers."""

from typing import BinaryIO, Protocol

from packages.models.domain.storage import StorageAsset


class StorageProvider(Protocol):
    """Provides provider-neutral access to stored dataset assets."""

    def describe(self, reference: str) -> StorageAsset:
        """Return canonical metadata for the asset identified by ``reference``."""

    def open_binary(self, reference: str) -> BinaryIO:
        """Open the asset identified by ``reference`` for binary reading."""
