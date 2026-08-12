"""Shared exceptions used by Athena domain and infrastructure code."""


class StorageAssetNotFoundError(FileNotFoundError):
    """Raised when a storage provider cannot locate an asset."""


class InvalidStorageReferenceError(ValueError):
    """Raised when an asset reference is invalid for a storage provider."""


class DatasetNotFoundError(LookupError):
    """Raised when a requested dataset is absent from the dataset repository."""


class CSVLoadError(ValueError):
    """Raised when CSV content or CSV loader options cannot be parsed."""


class ExcelLoadError(ValueError):
    """Raised when Excel content or Excel loader options cannot be parsed."""


class UnsupportedDatasetFormatError(ValueError):
    """Raised when Athena has no loader for a registered dataset format."""


class QueryExecutionError(ValueError):
    """Raised when a query engine cannot execute a SQL statement."""


class QueryResourceLimitError(QueryExecutionError):
    """Raised when a query exceeds an established execution resource limit."""
