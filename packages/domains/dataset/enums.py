from enum import Enum


class DatasetStatus(str, Enum):
    """Lifecycle state of a dataset."""

    NEW = "new"
    REGISTERED = "registered"
    PROFILED = "profiled"
    VALIDATED = "validated"
    READY = "ready"
    ARCHIVED = "archived"