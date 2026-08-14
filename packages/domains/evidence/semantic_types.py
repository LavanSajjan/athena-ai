"""Semantic types for column interpretation."""

from enum import StrEnum


class SemanticType(StrEnum):
    IDENTIFIER = "identifier"
    TEMPORAL = "temporal"
    MEASURE = "measure"
    CATEGORICAL = "categorical"
    TEXT = "text"
    UNKNOWN = "unknown"
