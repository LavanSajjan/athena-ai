"""Shared exceptions used by Athena domain and infrastructure code."""


class StorageAssetNotFoundError(FileNotFoundError):
    """Raised when a storage provider cannot locate an asset."""


class InvalidStorageReferenceError(ValueError):
    """Raised when an asset reference is invalid for a storage provider."""


class DatasetNotFoundError(LookupError):
    """Raised when a requested dataset is absent from the registry."""
