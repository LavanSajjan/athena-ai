"""Evidence domain models — immutable, structured observations."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class EvidenceType(StrEnum):
    """WHAT was observed or asserted."""

    DATA_TYPE = "data_type"
    NULL_RATE = "null_rate"
    CARDINALITY = "cardinality"
    UNIQUENESS = "uniqueness"
    NAME_PATTERN = "name_pattern"
    VALUE_RANGE = "value_range"
    TEMPORAL_PATTERN = "temporal_pattern"
    DUPLICATE_PATTERN = "duplicate_pattern"


class EvidenceSource(StrEnum):
    """WHO/WHAT supplied the evidence — a dimension independent of type."""

    SYSTEM = "system"
    USER = "user"


@dataclass(frozen=True, slots=True)
class Evidence:
    """An immutable, structured, auditable observation."""

    id: UUID
    dataset_id: UUID
    analysis_run_id: UUID
    column_name: str | None  # None => dataset-level evidence
    evidence_type: EvidenceType
    source: EvidenceSource
    producer: str  # e.g. "profiler.v1", "semantic_typer.v1", "user.explicit"
    details: dict[str, Any]  # structured, serializable observation payload
    description: str  # human-explainable summary
    created_at: datetime

    @staticmethod
    def create(
        *,
        dataset_id: UUID,
        analysis_run_id: UUID,
        evidence_type: EvidenceType,
        source: EvidenceSource,
        producer: str,
        details: dict[str, Any],
        description: str,
        created_at: datetime,
        column_name: str | None = None,
    ) -> "Evidence":
        return Evidence(
            id=uuid4(),
            dataset_id=dataset_id,
            analysis_run_id=analysis_run_id,
            column_name=column_name,
            evidence_type=evidence_type,
            source=source,
            producer=producer,
            details=details,
            description=description,
            created_at=created_at,
        )
