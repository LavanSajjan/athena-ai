"""Tests for the Evidence domain model and its value types."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from packages.domains.evidence.confidence import Confidence
from packages.domains.evidence.interpretation import (
    AlternativeInterpretation,
    ColumnInterpretation,
)
from packages.domains.evidence.models import Evidence, EvidenceSource, EvidenceType
from packages.domains.evidence.semantic_types import SemanticType


def _make_evidence(**overrides: Any) -> Evidence:
    """Build an Evidence instance with sensible defaults for testing."""
    defaults: dict[str, Any] = dict(
        dataset_id=uuid4(),
        analysis_run_id=uuid4(),
        evidence_type=EvidenceType.DATA_TYPE,
        source=EvidenceSource.SYSTEM,
        producer="profiler.v1",
        details={"physical_type": "Float64"},
        description="a data type observation",
        created_at=datetime.now(UTC),
        column_name="amount",
    )
    defaults.update(overrides)
    return Evidence.create(**defaults)


def test_evidence_type_has_expected_variants() -> None:
    """All evidence types from the ADR must be present for future producers."""
    assert EvidenceType.DATA_TYPE.value == "data_type"
    assert EvidenceType.NULL_RATE.value == "null_rate"
    assert EvidenceType.CARDINALITY.value == "cardinality"
    assert EvidenceType.UNIQUENESS.value == "uniqueness"
    assert EvidenceType.NAME_PATTERN.value == "name_pattern"
    assert EvidenceType.VALUE_RANGE.value == "value_range"
    assert EvidenceType.TEMPORAL_PATTERN.value == "temporal_pattern"
    assert EvidenceType.DUPLICATE_PATTERN.value == "duplicate_pattern"


def test_evidence_source_has_system_and_user_variants() -> None:
    """Source must distinguish system-originated from user-originated evidence."""
    assert EvidenceSource.SYSTEM.value == "system"
    assert EvidenceSource.USER.value == "user"


def test_evidence_create_assigns_distinct_id_per_construction() -> None:
    """Each Evidence must get a unique identity, never reused."""
    first = _make_evidence()
    second = _make_evidence()

    assert first.id != second.id
    assert isinstance(first.id, UUID)
    assert isinstance(second.id, UUID)


def test_evidence_preserves_all_scoping_fields() -> None:
    """dataset_id, analysis_run_id, and column_name must propagate exactly."""
    dataset_id = uuid4()
    analysis_run_id = uuid4()

    evidence = _make_evidence(
        dataset_id=dataset_id,
        analysis_run_id=analysis_run_id,
        column_name="user_id",
    )

    assert evidence.dataset_id == dataset_id
    assert evidence.analysis_run_id == analysis_run_id
    assert evidence.column_name == "user_id"


def test_evidence_allows_dataset_level_when_column_name_is_none() -> None:
    """Dataset-level evidence is represented with column_name=None."""
    evidence = _make_evidence(column_name=None)

    assert evidence.column_name is None


def test_evidence_preserves_type_source_producer_and_details() -> None:
    """The three independent dimensions must not be collapsed."""
    evidence = _make_evidence(
        evidence_type=EvidenceType.NULL_RATE,
        source=EvidenceSource.USER,
        producer="user.explicit",
        details={"null_count": 0, "row_count": 100, "null_percentage": 0.0},
    )

    assert evidence.evidence_type == EvidenceType.NULL_RATE
    assert evidence.source == EvidenceSource.USER
    assert evidence.producer == "user.explicit"
    assert evidence.details == {"null_count": 0, "row_count": 100, "null_percentage": 0.0}


def test_evidence_is_immutable() -> None:
    """Frozen semantics: no field reassignment after construction."""
    evidence = _make_evidence()

    with pytest.raises(FrozenInstanceError):
        evidence.dataset_id = uuid4()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        evidence.details = {}  # type: ignore[misc]


def test_semantic_type_has_expected_variants() -> None:
    """Semantic types cover the deterministic classification space."""
    assert SemanticType.IDENTIFIER.value == "identifier"
    assert SemanticType.TEMPORAL.value == "temporal"
    assert SemanticType.MEASURE.value == "measure"
    assert SemanticType.CATEGORICAL.value == "categorical"
    assert SemanticType.TEXT.value == "text"
    assert SemanticType.UNKNOWN.value == "unknown"


def test_column_interpretation_cites_supporting_evidence_by_id() -> None:
    """Every interpretation must be traceable back to its supporting evidence."""
    dataset_id = uuid4()
    analysis_run_id = uuid4()
    evidence_id = uuid4()
    confidence = Confidence.from_score(0.91)
    alternative = AlternativeInterpretation(
        semantic_type=SemanticType.CATEGORICAL,
        confidence=Confidence.from_score(0.3),
    )

    interpretation = ColumnInterpretation(
        dataset_id=dataset_id,
        analysis_run_id=analysis_run_id,
        column_name="user_id",
        semantic_type=SemanticType.IDENTIFIER,
        confidence=confidence,
        supporting_evidence_ids=(evidence_id,),
        alternative_interpretations=(alternative,),
        producer="semantic_typer.v1",
    )

    assert interpretation.dataset_id == dataset_id
    assert interpretation.analysis_run_id == analysis_run_id
    assert interpretation.column_name == "user_id"
    assert interpretation.semantic_type == SemanticType.IDENTIFIER
    assert interpretation.confidence == confidence
    assert interpretation.supporting_evidence_ids == (evidence_id,)
    assert interpretation.alternative_interpretations == (alternative,)
    assert interpretation.producer == "semantic_typer.v1"


def test_column_interpretation_defaults_to_empty_limitations() -> None:
    """No limitations provided means an empty tuple, never None."""
    evidence = _make_evidence()
    interpretation = ColumnInterpretation(
        dataset_id=evidence.dataset_id,
        analysis_run_id=evidence.analysis_run_id,
        column_name="a",
        semantic_type=SemanticType.UNKNOWN,
        confidence=Confidence.insufficient(),
        supporting_evidence_ids=(),
        alternative_interpretations=(),
        producer="semantic_typer.v1",
    )

    assert interpretation.limitations == ()


def test_column_interpretation_is_immutable() -> None:
    """Interpretation results must not be mutable after creation."""
    evidence = _make_evidence()
    interpretation = ColumnInterpretation(
        dataset_id=evidence.dataset_id,
        analysis_run_id=evidence.analysis_run_id,
        column_name="a",
        semantic_type=SemanticType.UNKNOWN,
        confidence=Confidence.insufficient(),
        supporting_evidence_ids=(),
        alternative_interpretations=(),
        producer="semantic_typer.v1",
    )

    with pytest.raises(FrozenInstanceError):
        interpretation.semantic_type = SemanticType.TEXT  # type: ignore[misc]
