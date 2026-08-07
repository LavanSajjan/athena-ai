"""Local filesystem implementation of the storage provider port."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from packages.interfaces.storage import StorageProvider
from packages.models.domain.storage import StorageAsset
from packages.shared.exceptions import (
    InvalidStorageReferenceError,
    StorageAssetNotFoundError,
)


class LocalStorageProvider(StorageProvider):
    """Provide storage access to regular files below a configured root directory."""

    _HASH_CHUNK_SIZE = 1024 * 1024

    def __init__(self, storage_root: Path) -> None:
        """Initialize the provider with the directory containing allowed assets."""
        self.storage_root = storage_root.resolve()

    def describe(self, reference: str) -> StorageAsset:
        """Return metadata and a SHA-256 digest for the referenced local asset."""
        path = self._resolve_reference(reference)

        return StorageAsset(
            reference=reference,
            name=path.stem,
            extension=path.suffix.removeprefix(".").lower(),
            uri=path.as_uri(),
            size_bytes=path.stat().st_size,
            sha256=self._calculate_sha256(path),
        )

    def open_binary(self, reference: str) -> BinaryIO:
        """Open the referenced local asset for binary reading."""
        return self._resolve_reference(reference).open("rb")

    def _resolve_reference(self, reference: str) -> Path:
        """Resolve and validate a provider-relative reference beneath the storage root."""
        if not reference:
            raise InvalidStorageReferenceError("Storage reference must not be empty.")

        candidate = Path(reference)

        if candidate.is_absolute():
            raise InvalidStorageReferenceError(
                "Storage reference must be relative to the configured storage root."
            )

        path = (self.storage_root / candidate).resolve()

        try:
            path.relative_to(self.storage_root)
        except ValueError as error:
            raise InvalidStorageReferenceError(
                "Storage reference resolves outside the configured storage root."
            ) from error

        if not path.exists():
            raise StorageAssetNotFoundError(reference)

        if not path.is_file():
            raise InvalidStorageReferenceError("Storage reference must identify a regular file.")

        return path

    def _calculate_sha256(self, path: Path) -> str:
        """Return the SHA-256 digest of ``path`` while streaming fixed-size chunks."""
        digest = hashlib.sha256()

        with path.open("rb") as asset_file:
            while chunk := asset_file.read(self._HASH_CHUNK_SIZE):
                digest.update(chunk)

        return digest.hexdigest()
