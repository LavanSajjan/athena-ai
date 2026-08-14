"""Port for recording and retrieving immutable Evidence."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from packages.domains.evidence.models import Evidence


@runtime_checkable
class EvidenceStore(Protocol):
    """Append-only store of immutable Evidence observations.

    Recording a new Evidence item never replaces or deletes previously
    recorded Evidence; every ``record`` call extends the history. The store is
    knowledge, not notification — it is deliberately not an event bus.
    """

    def record(self, evidence: Evidence) -> None:
        """Append one Evidence item. Never overwrites or removes existing Evidence."""
        ...

    def for_dataset(self, dataset_id: UUID) -> tuple[Evidence, ...]:
        """Return all Evidence for a dataset, across every analysis run."""
        ...

    def for_column(self, dataset_id: UUID, column_name: str) -> tuple[Evidence, ...]:
        """Return all Evidence for one column of a dataset, across every run."""
        ...
