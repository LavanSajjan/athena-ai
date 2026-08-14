"""Column interpretation models — evidence-backed semantic claims."""

from dataclasses import dataclass
from uuid import UUID

from packages.domains.evidence.confidence import Confidence
from packages.domains.evidence.semantic_types import SemanticType


@dataclass(frozen=True, slots=True)
class AlternativeInterpretation:
    semantic_type: SemanticType
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class ColumnInterpretation:
    """Athena's current best interpretation of one column's meaning."""

    dataset_id: UUID
    analysis_run_id: UUID
    column_name: str
    semantic_type: SemanticType
    confidence: Confidence
    supporting_evidence_ids: tuple[UUID, ...]
    alternative_interpretations: tuple[AlternativeInterpretation, ...]
    producer: str
    limitations: tuple[str, ...] = ()
