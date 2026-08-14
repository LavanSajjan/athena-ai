"""Focused tests for the in-memory EvidenceStore adapter."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from packages.adapters.evidence.in_memory_evidence_store import InMemoryEvidenceStore
from packages.domains.evidence.models import Evidence, EvidenceSource, EvidenceType
from packages.interfaces.evidence_store import EvidenceStore


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


def test_record_stores_evidence() -> None:
    """A recorded Evidence item is retrievable via for_dataset."""
    store = InMemoryEvidenceStore()
    evidence = _make_evidence()

    store.record(evidence)

    assert store.for_dataset(evidence.dataset_id) == (evidence,)


def test_multiple_evidence_for_same_dataset_all_retained() -> None:
    """Every Evidence item for a dataset survives subsequent recordings."""
    dataset_id = uuid4()
    first = _make_evidence(dataset_id=dataset_id, column_name="a")
    second = _make_evidence(dataset_id=dataset_id, column_name="b")
    third = _make_evidence(dataset_id=dataset_id, column_name="c")
    store = InMemoryEvidenceStore()

    store.record(first)
    store.record(second)
    store.record(third)

    result = store.for_dataset(dataset_id)
    assert result == (first, second, third)
    assert len(result) == 3


def test_recording_second_evidence_does_not_replace_first() -> None:
    """A second record() must append, not overwrite, the existing item."""
    dataset_id = uuid4()
    first = _make_evidence(dataset_id=dataset_id, column_name="a")
    second = _make_evidence(dataset_id=dataset_id, column_name="b")
    store = InMemoryEvidenceStore()

    store.record(first)
    store.record(second)

    result = store.for_dataset(dataset_id)
    assert first in result
    assert second in result
    assert result[0] is first


def test_for_dataset_returns_evidence_for_requested_dataset_only() -> None:
    """for_dataset must return the requested dataset's evidence in full."""
    dataset_a = uuid4()
    dataset_b = uuid4()
    a_first = _make_evidence(dataset_id=dataset_a, column_name="a")
    a_second = _make_evidence(dataset_id=dataset_a, column_name="b")
    b_first = _make_evidence(dataset_id=dataset_b, column_name="x")
    store = InMemoryEvidenceStore()

    store.record(a_first)
    store.record(a_second)
    store.record(b_first)

    assert store.for_dataset(dataset_a) == (a_first, a_second)


def test_for_dataset_excludes_evidence_from_another_dataset() -> None:
    """for_dataset for one dataset must not leak another dataset's evidence."""
    dataset_a = uuid4()
    dataset_b = uuid4()
    a_first = _make_evidence(dataset_id=dataset_a, column_name="a")
    b_first = _make_evidence(dataset_id=dataset_b, column_name="x")
    store = InMemoryEvidenceStore()

    store.record(a_first)
    store.record(b_first)

    assert b_first not in store.for_dataset(dataset_a)
    assert b_first in store.for_dataset(dataset_b)


def test_for_column_returns_only_evidence_for_exact_column() -> None:
    """for_column must match the dataset and the exact column name only."""
    dataset_id = uuid4()
    user_id = _make_evidence(dataset_id=dataset_id, column_name="user_id")
    amount = _make_evidence(dataset_id=dataset_id, column_name="amount")
    store = InMemoryEvidenceStore()

    store.record(user_id)
    store.record(amount)

    assert store.for_column(dataset_id, "user_id") == (user_id,)
    assert user_id in store.for_column(dataset_id, "user_id")
    assert amount not in store.for_column(dataset_id, "user_id")


def test_for_dataset_returns_dataset_level_evidence() -> None:
    """Dataset-level evidence (column_name=None) is visible through for_dataset."""
    dataset_id = uuid4()
    dataset_level = _make_evidence(dataset_id=dataset_id, column_name=None)
    store = InMemoryEvidenceStore()

    store.record(dataset_level)

    result = store.for_dataset(dataset_id)
    assert dataset_level in result
    assert result == (dataset_level,)


def test_for_column_excludes_dataset_level_evidence() -> None:
    """Dataset-level evidence (column_name=None) must not appear in any for_column."""
    dataset_id = uuid4()
    dataset_level = _make_evidence(dataset_id=dataset_id, column_name=None)
    column_level = _make_evidence(dataset_id=dataset_id, column_name="user_id")
    store = InMemoryEvidenceStore()

    store.record(dataset_level)
    store.record(column_level)

    result = store.for_column(dataset_id, "user_id")
    assert column_level in result
    assert dataset_level not in result


def test_results_are_tuples_that_cannot_mutate_internal_collection() -> None:
    """Returned collections are immutable tuples that snapshot the store state."""
    dataset_id = uuid4()
    first = _make_evidence(dataset_id=dataset_id, column_name="a")
    second = _make_evidence(dataset_id=dataset_id, column_name="b")
    store = InMemoryEvidenceStore()

    store.record(first)
    snapshot = store.for_dataset(dataset_id)

    assert isinstance(snapshot, tuple)
    # A previously returned snapshot must not change when more evidence is added.
    store.record(second)
    assert snapshot == (first,)
    assert store.for_dataset(dataset_id) == (first, second)

    column_snapshot = store.for_column(dataset_id, "a")
    assert isinstance(column_snapshot, tuple)
    assert column_snapshot == (first,)


def test_insertion_order_is_preserved() -> None:
    """for_dataset and for_column must preserve the order evidence was recorded."""
    dataset_id = uuid4()
    first = _make_evidence(dataset_id=dataset_id, column_name="a")
    second = _make_evidence(dataset_id=dataset_id, column_name="b")
    third = _make_evidence(dataset_id=dataset_id, column_name="c")
    store = InMemoryEvidenceStore()

    store.record(first)
    store.record(second)
    store.record(third)

    assert store.for_dataset(dataset_id) == (first, second, third)
    assert store.for_column(dataset_id, "b") == (second,)


def test_empty_queries_return_empty_tuple() -> None:
    """Unknown datasets and absent columns must yield empty tuples."""
    store = InMemoryEvidenceStore()

    assert store.for_dataset(uuid4()) == ()
    assert store.for_column(uuid4(), "missing") == ()


@pytest.mark.parametrize(
    "method_name",
    ["record", "for_dataset", "for_column"],
)
def test_adapter_satisfies_evidence_store_protocol(method_name: str) -> None:
    """The adapter must structurally satisfy the EvidenceStore Protocol."""
    store = InMemoryEvidenceStore()

    assert isinstance(store, EvidenceStore)
    assert hasattr(store, method_name)
