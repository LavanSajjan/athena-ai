from enum import StrEnum


class DatasetStatus(StrEnum):
    """Lifecycle state of a dataset."""

    NEW = "new"
    REGISTERED = "registered"
    PROFILED = "profiled"
    VALIDATED = "validated"
    READY = "ready"
    ARCHIVED = "archived"