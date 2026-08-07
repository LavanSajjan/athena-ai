"""Provider-neutral models describing stored assets."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StorageAsset:
    """Canonical metadata for an asset supplied by a storage provider."""

    reference: str
    name: str
    extension: str
    uri: str
    size_bytes: int
    sha256: str
