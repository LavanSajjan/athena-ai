"""Tests for :meth:`DatasetProfiler.collect_evidence`.

These tests treat ``collect_evidence`` as the ADR-0011 translation layer: it
consumes an already-computed ``ProfileResult`` and emits ``Evidence`` without
performing new dataframe analysis, semantic interpretation, or persistence.
"""

import inspect
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import polars as pl
import pytest

from packages.domains.evidence.models import Evidence, EvidenceSource, EvidenceType
from packages.loaders.models import TabularLoadResult
from packages.models.domain.storage import StorageAsset
from packages.profiling.models import (
    ColumnProfile,
    DataQualityProfile,
    DatasetSummary,
    ProfileRecommendations,
    ProfileResult,
)
from packages.profiling.profiler import DatasetProfiler

PRODUCER = "profiler.v1"

# Names the profiler's existing identifier-name heuristic matches (name-set OR a
# "_id"/"_key"/"_code"/"_uuid" suffix). "CustomerId" is intentionally excluded:
# it lower-cases to "customerid", which neither is in the name-set nor ends with
# "_id" — this mirrors _is_identifier_name exactly.
_NAMED_PATTERNS = ["id", "user_id", "order_key", "category_code", "uuid"]
_NON_IDENTIFIER_PATTERNS = ["segment", "amount", "name", "created_at", "Date"]


def _column_profile(name: str, data_type: str, **kwargs: Any) -> ColumnProfile:
    """Build a ColumnProfile with defaults for the nullable/numeric fields."""
    defaults: dict[str, Any] = dict(
        null_count=0,
        null_percentage=0.0,
        distinct_count=1,
        distinct_percentage=100.0,
    )
    defaults.update(kwargs)
    return ColumnProfile(name=name, data_type=data_type, **defaults)


def _profile_result(
    columns: tuple[ColumnProfile, ...],
    row_count: int,
    *,
    duplicate_row_count: int = 0,
    duplicate_row_percentage: float = 0.0,
    date_dimensions: tuple[str, ...] = (),
) -> ProfileResult:
    """Assemble a ProfileResult by hand — no dataframe, loader, or storage.

    This fixture exists specifically to prove ``collect_evidence`` depends only
    on ``ProfileResult`` and the supplied identifiers, never on raw data.
    """
    return ProfileResult(
        summary=DatasetSummary(
            reference="memory/test.csv",
            name="test",
            row_count=row_count,
            column_count=len(columns),
            estimated_size_bytes=0,
        ),
        columns=columns,
        data_quality=DataQualityProfile(
            total_cell_count=row_count * len(columns),
            null_cell_count=sum(column.null_count for column in columns),
            null_percentage=0.0,
            duplicate_row_count=duplicate_row_count,
            duplicate_row_percentage=duplicate_row_percentage,
            empty_column_count=0,
        ),
        recommendations=ProfileRecommendations(
            potential_primary_keys=(),
            identifier_columns=(),
            categorical_columns=(),
            numeric_measures=(),
            date_dimensions=date_dimensions,
        ),
    )


def _load_result(dataframe: pl.DataFrame) -> TabularLoadResult:
    """Build a loaded-table result without touching the filesystem."""
    return TabularLoadResult(
        asset=StorageAsset(
            reference="memory/sales.csv",
            name="sales",
            extension="csv",
            uri="memory://sales.csv",
            size_bytes=128,
            sha256="a" * 64,
        ),
        dataframe=dataframe,
        row_count=dataframe.height,
        column_count=dataframe.width,
        column_names=dataframe.columns,
        estimated_size_bytes=int(dataframe.estimated_size()),
    )


def _collect(result: ProfileResult) -> tuple[Evidence, ...]:
    profiler = DatasetProfiler()
    return profiler.collect_evidence(uuid4(), uuid4(), result)


# ---------------------------------------------------------------------------
# Signature & provenance (rules 1, 8, 12)
# ---------------------------------------------------------------------------


def test_collect_evidence_has_required_signature_parameters() -> None:
    """The caller supplies dataset_id and analysis_run_id; the profiler never generates it."""
    parameters = list(inspect.signature(DatasetProfiler.collect_evidence).parameters)
    assert parameters == ["self", "dataset_id", "analysis_run_id", "result"]
    assert (
        inspect.signature(DatasetProfiler.collect_evidence).return_annotation
        == tuple[Evidence, ...]
    )


def test_collect_evidence_does_not_generate_analysis_run_id_internally() -> None:
    """analysis_run_id must flow through untouched — never uuid4'd inside."""
    supplied_run = uuid4()
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=4),), row_count=4
    )
    evidence = DatasetProfiler().collect_evidence(uuid4(), supplied_run, result)

    assert all(e.analysis_run_id == supplied_run for e in evidence)
    assert len({e.analysis_run_id for e in evidence}) == 1


# ---------------------------------------------------------------------------
# Per-evidence-type translation (rules 1, 2, 3, 4, 7)
# ---------------------------------------------------------------------------


def test_data_type_evidence_emitted_for_each_column() -> None:
    """One DATA_TYPE evidence per column, carrying its physical type."""
    result = _profile_result(
        columns=(
            _column_profile("user_id", "Int64", distinct_count=4),
            _column_profile("amount", "Float64", distinct_count=3),
        ),
        row_count=4,
    )
    evidence = _collect(result)

    data_types = [e for e in evidence if e.evidence_type == EvidenceType.DATA_TYPE]
    assert len(data_types) == 2
    by_name = {e.column_name: e for e in data_types}
    assert by_name["user_id"].details == {"physical_type": "Int64"}
    assert by_name["amount"].details == {"physical_type": "Float64"}
    for item in data_types:
        assert item.producer == PRODUCER
        assert item.source == EvidenceSource.SYSTEM
        assert item.column_name in {"user_id", "amount"}


def test_null_rate_evidence_reflects_actual_null_values() -> None:
    """NULL_RATE details carry the real null_count, row_count, null_percentage."""
    result = _profile_result(
        columns=(
            _column_profile("a", "String", null_count=0, null_percentage=0.0),
            _column_profile("b", "String", null_count=2, null_percentage=50.0),
        ),
        row_count=4,
    )
    evidence = _collect(result)

    null_rates = {e.column_name: e for e in evidence if e.evidence_type == EvidenceType.NULL_RATE}
    assert null_rates["a"].details == {"null_count": 0, "row_count": 4, "null_percentage": 0.0}
    assert null_rates["b"].details == {"null_count": 2, "row_count": 4, "null_percentage": 50.0}


def test_cardinality_evidence_reflects_distinct_counts() -> None:
    """CARDINALITY details carry the real distinct_count, row_count, distinct_percentage."""
    result = _profile_result(
        columns=(
            _column_profile("a", "String", distinct_count=1, distinct_percentage=25.0),
            _column_profile("b", "String", distinct_count=4, distinct_percentage=100.0),
        ),
        row_count=4,
    )
    evidence = _collect(result)

    cardinalities = {
        e.column_name: e for e in evidence if e.evidence_type == EvidenceType.CARDINALITY
    }
    assert cardinalities["a"].details == {
        "distinct_count": 1,
        "row_count": 4,
        "distinct_percentage": 25.0,
    }
    assert cardinalities["b"].details == {
        "distinct_count": 4,
        "row_count": 4,
        "distinct_percentage": 100.0,
    }


def test_uniqueness_emitted_only_when_distinct_equals_row_count() -> None:
    """UNIQUENESS is a positive observation: distinct_count == row_count only."""
    result = _profile_result(
        columns=(
            _column_profile("unique_id", "Int64", distinct_count=4),
            _column_profile("repeater", "String", distinct_count=1, null_count=0),
            _column_profile("partial", "String", distinct_count=3),
        ),
        row_count=4,
    )
    evidence = _collect(result)

    uniqueness_columns = {
        e.column_name for e in evidence if e.evidence_type == EvidenceType.UNIQUENESS
    }
    assert uniqueness_columns == {"unique_id"}
    for item in evidence:
        if item.evidence_type == EvidenceType.UNIQUENESS:
            assert item.details == {
                "distinct_count": 4,
                "row_count": 4,
                "is_unique": True,
            }


def test_uniqueness_not_emitted_for_empty_dataset() -> None:
    """Vacuously unique columns (zero rows) must not produce UNIQUENESS evidence."""
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=0),), row_count=0
    )
    evidence = _collect(result)

    assert not any(e.evidence_type == EvidenceType.UNIQUENESS for e in evidence)


def test_name_pattern_emitted_only_for_identifier_names() -> None:
    """NAME_PATTERN reflects the name heuristic; non-matches emit nothing."""
    result = _profile_result(
        columns=(
            _column_profile("user_id", "Int64", distinct_count=4),
            _column_profile("order_key", "Int64", distinct_count=4),
            _column_profile("amount", "Float64", distinct_count=3),
            _column_profile("segment", "String", distinct_count=2),
        ),
        row_count=4,
    )
    evidence = _collect(result)

    name_patterns = {
        e.column_name: e for e in evidence if e.evidence_type == EvidenceType.NAME_PATTERN
    }
    assert set(name_patterns) == {"user_id", "order_key"}
    assert name_patterns["user_id"].details == {"matched_pattern": "suffix:_id"}
    assert name_patterns["order_key"].details == {"matched_pattern": "suffix:_key"}


@pytest.mark.parametrize("column_name", _NAMED_PATTERNS)
def test_name_pattern_descriptor_is_specific(column_name: str) -> None:
    """The matched_pattern detail names the rule that actually applied."""
    result = _profile_result(
        columns=(_column_profile(column_name, "Int64", distinct_count=4),), row_count=4
    )
    evidence = _collect(result)

    name_patterns = [e for e in evidence if e.evidence_type == EvidenceType.NAME_PATTERN]
    assert len(name_patterns) == 1
    assert name_patterns[0].details["matched_pattern"] in {
        "name:id",
        "name:key",
        "name:uuid",
        "name:identifier",
        "name:code",
        "name:category",
        "name:customerid",
        "suffix:_id",
        "suffix:_key",
        "suffix:_code",
        "suffix:_uuid",
    }


@pytest.mark.parametrize("column_name", _NON_IDENTIFIER_PATTERNS)
def test_name_pattern_not_emitted_for_non_identifiers(column_name: str) -> None:
    """Columns whose names do not match the heuristic emit no NAME_PATTERN."""
    result = _profile_result(
        columns=(_column_profile(column_name, "String", distinct_count=4),),
        row_count=4,
    )
    evidence = _collect(result)

    assert not any(
        e.evidence_type == EvidenceType.NAME_PATTERN and e.column_name == column_name
        for e in evidence
    )


# ---------------------------------------------------------------------------
# No-fabrication rules (9, 14)
# ---------------------------------------------------------------------------


def test_no_temporal_pattern_for_float64_excel_like_values() -> None:
    """A Float64 column named 'Date' (e.g. 46054) is data_type, never temporal."""
    result = _profile_result(
        columns=(_column_profile("Date", "Float64", distinct_count=1),),
        row_count=4,
        date_dimensions=(),
    )
    evidence = _collect(result)

    types = {e.evidence_type for e in evidence}
    assert EvidenceType.TEMPORAL_PATTERN not in types
    data_type = next(e for e in evidence if e.evidence_type == EvidenceType.DATA_TYPE)
    assert data_type.details == {"physical_type": "Float64"}


def test_no_value_range_evidence_is_ever_emitted() -> None:
    """VALUE_RANGE has no current producer; collect_evidence must never fabricate it."""
    result = _profile_result(
        columns=(_column_profile("amount", "Float64", distinct_count=4),),
        row_count=4,
        date_dimensions=("created_at",),
    )
    evidence = _collect(result)

    assert not any(e.evidence_type == EvidenceType.VALUE_RANGE for e in evidence)
    assert all(e.evidence_type != EvidenceType.VALUE_RANGE for e in evidence)


def test_temporal_pattern_for_native_date_type_only() -> None:
    """TEMPORAL is emitted only for native date/datetime physical types."""
    result = _profile_result(
        columns=(
            _column_profile("birthday", "Date", distinct_count=4),
            _column_profile("amount", "Float64", distinct_count=4),
        ),
        row_count=4,
        date_dimensions=("birthday",),
    )
    evidence = _collect(result)

    temporals = [e for e in evidence if e.evidence_type == EvidenceType.TEMPORAL_PATTERN]
    assert {e.column_name for e in temporals} == {"birthday"}
    assert temporals[0].details == {"physical_type": "Date"}


# ---------------------------------------------------------------------------
# Scoping & batch invariants (rules 6, 7, 8, 9, 10)
# ---------------------------------------------------------------------------


def test_duplicate_pattern_is_dataset_level_evidence() -> None:
    """DUPLICATE_PATTERN is dataset-level: column_name is None."""
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=4),),
        row_count=4,
        duplicate_row_count=1,
        duplicate_row_percentage=25.0,
    )
    evidence = _collect(result)

    duplicates = [e for e in evidence if e.evidence_type == EvidenceType.DUPLICATE_PATTERN]
    assert len(duplicates) == 1
    assert duplicates[0].column_name is None
    assert duplicates[0].details == {
        "duplicate_row_count": 1,
        "duplicate_row_percentage": 25.0,
    }


def test_dataset_level_evidence_has_no_column_name() -> None:
    """Every DUPLICATE_PATTERN item is the only dataset-level evidence."""
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=4),),
        row_count=4,
    )
    evidence = _collect(result)

    dataset_level = [e for e in evidence if e.column_name is None]
    assert len(dataset_level) == 1
    assert dataset_level[0].evidence_type == EvidenceType.DUPLICATE_PATTERN


def test_every_evidence_item_carry_required_provenance() -> None:
    """Each item has dataset_id, analysis_run_id, producer, created_at, column_name."""
    dataset_id = uuid4()
    analysis_run_id = uuid4()
    result = _profile_result(
        columns=(_column_profile("user_id", "Int64", distinct_count=4),),
        row_count=4,
        date_dimensions=(),
        duplicate_row_count=2,
    )
    evidence = DatasetProfiler().collect_evidence(dataset_id, analysis_run_id, result)

    assert len(evidence) > 0
    for item in evidence:
        assert item.dataset_id == dataset_id
        assert item.analysis_run_id == analysis_run_id
        assert item.producer == PRODUCER
        assert item.source == EvidenceSource.SYSTEM
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.details, dict)
        assert isinstance(item.description, str) and item.description
        if item.evidence_type == EvidenceType.DUPLICATE_PATTERN:
            assert item.column_name is None
        else:
            assert item.column_name == "user_id"


def test_single_created_at_timestamp_per_invocation() -> None:
    """All evidence from one call shares one created_at timestamp."""
    result = _profile_result(
        columns=(
            _column_profile("a", "Int64", distinct_count=4),
            _column_profile("b", "String", distinct_count=2),
        ),
        row_count=4,
        date_dimensions=("b",),
    )
    evidence = _collect(result)

    timestamps = {e.created_at for e in evidence}
    assert len(timestamps) == 1


def test_evidence_is_scoped_to_the_supplied_analysis_run() -> None:
    """Different analysis_run_id values keep evidence in separate runs."""
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=4),),
        row_count=4,
    )
    dataset_id = uuid4()
    run_a = uuid4()
    run_b = uuid4()

    a = DatasetProfiler().collect_evidence(dataset_id, run_a, result)
    b = DatasetProfiler().collect_evidence(dataset_id, run_b, result)

    assert {e.analysis_run_id for e in a} == {run_a}
    assert {e.analysis_run_id for e in b} == {run_b}
    assert all(e.dataset_id == dataset_id for e in a)
    assert all(e.dataset_id == dataset_id for e in b)
    assert len(a) == len(b) > 0


def test_two_invocations_produce_distinct_evidence_ids() -> None:
    """Evidence is append-only: separate runs never alias the same id."""
    result = _profile_result(
        columns=(_column_profile("id", "Int64", distinct_count=4),),
        row_count=4,
    )
    first = DatasetProfiler().collect_evidence(uuid4(), uuid4(), result)
    second = DatasetProfiler().collect_evidence(uuid4(), uuid4(), result)

    assert {e.id for e in first}.isdisjoint({e.id for e in second})


# ---------------------------------------------------------------------------
# No-dataframe / no-storage rule (rule 22) + detail serialization (rules 13)
# ---------------------------------------------------------------------------


def test_collect_evidence_works_from_profile_result_alone() -> None:
    """collect_evidence must not depend on a loader, storage, DuckDB, or raw df.

    The ProfileResult here is assembled by hand — no dataframe ever exists.
    """
    result = _profile_result(
        columns=(
            _column_profile("created_at", "Date", distinct_count=4),
            _column_profile("amount", "Float64", distinct_count=3),
        ),
        row_count=4,
        date_dimensions=("created_at",),
    )

    evidence = DatasetProfiler().collect_evidence(uuid4(), uuid4(), result)

    assert len(evidence) > 0


def test_collect_evidence_details_are_json_serializable_primitives() -> None:
    """details must contain only structured, JSON-compatible primitive values."""
    result = _profile_result(
        columns=(
            _column_profile("user_id", "Int64", distinct_count=4),
            _column_profile("created_at", "Date", distinct_count=4),
        ),
        row_count=4,
        date_dimensions=("created_at",),
        duplicate_row_count=1,
        duplicate_row_percentage=25.0,
    )
    evidence = _collect(result)

    for item in evidence:
        json.dumps(item.details)
        for value in item.details.values():
            assert isinstance(value, (str, int, float, bool, type(None)))


def test_collect_evidence_never_emits_user_source() -> None:
    """All profiler evidence is SYSTEM-sourced; no user assertions here."""
    result = _profile_result(
        columns=(_column_profile("user_id", "Int64", distinct_count=4),),
        row_count=4,
    )
    evidence = _collect(result)

    assert all(e.source == EvidenceSource.SYSTEM for e in evidence)
    assert all(e.producer == PRODUCER for e in evidence)


# ---------------------------------------------------------------------------
# Integration with the real profiler + divergence regression
# ---------------------------------------------------------------------------


def test_collect_evidence_from_real_profile_matches_observations() -> None:
    """End-to-end: profile() then collect_evidence() over a real dataframe."""
    dataframe = pl.DataFrame(
        {
            "user_id": [1, 2, 3, 4],
            "amount": [10.0, 20.0, 20.0, 30.0],
            "ordered_on": [
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
            ],
        },
        schema={
            "user_id": pl.Int64,
            "amount": pl.Float64,
            "ordered_on": pl.Date,
        },
    )
    profile = DatasetProfiler().profile(_load_result(dataframe))

    evidence = DatasetProfiler().collect_evidence(uuid4(), uuid4(), profile)

    # Three columns => three DATA_TYPE, NULL_RATE, CARDINALITY each.
    assert sum(1 for e in evidence if e.evidence_type == EvidenceType.DATA_TYPE) == 3
    # user_id is unique (4 distinct, 4 rows) and an identifier name.
    uniqueness = [e for e in evidence if e.evidence_type == EvidenceType.UNIQUENESS]
    assert {e.column_name for e in uniqueness} == {"user_id", "ordered_on"}
    # ordered_on is a native date dimension => TEMPORAL_PATTERN.
    temporals = [e for e in evidence if e.evidence_type == EvidenceType.TEMPORAL_PATTERN]
    assert {e.column_name for e in temporals} == {"ordered_on"}
    # user_id matches the identifier heuristic => NAME_PATTERN.
    name_patterns = [e for e in evidence if e.evidence_type == EvidenceType.NAME_PATTERN]
    assert {e.column_name for e in name_patterns} == {"user_id"}
    assert name_patterns[0].details == {"matched_pattern": "suffix:_id"}
    # No duplicate rows => DUPLICATE_PATTERN reports zero.
    duplicates = [e for e in evidence if e.evidence_type == EvidenceType.DUPLICATE_PATTERN]
    assert duplicates[0].details["duplicate_row_count"] == 0


def test_profiler_profile_behavior_is_unchanged_by_collect_evidence() -> None:
    """Adding collect_evidence must not alter profile()'s output."""
    dataframe = pl.DataFrame(
        {
            "order_id": [101, 102, 103, 104, 105],
            "status": ["new", "paid", "new", "paid", "paid"],
        },
        schema={"order_id": pl.Int64, "status": pl.String},
    )
    profiler = DatasetProfiler()
    before = profiler.profile(_load_result(dataframe))

    # Exercise the new method on the same result object.
    profiler.collect_evidence(uuid4(), uuid4(), before)

    after = profiler.profile(_load_result(dataframe))
    assert before == after


@pytest.mark.parametrize(
    "name",
    [
        "id",
        "key",
        "uuid",
        "identifier",
        "code",
        "UserId",
        "user_id",
        "order_key",
        "category_code",
        "event_uuid",
        "segment",
        "amount",
        "name",
        "status",
        "",
    ],
)
def test_identifier_pattern_and_helper_agree(name: str) -> None:
    """Regression guard: the two identifier-name signals never diverge."""
    profiler = DatasetProfiler()
    pattern = profiler._identifier_pattern(name)
    assert profiler._is_identifier_name(name) == (pattern is not None)
