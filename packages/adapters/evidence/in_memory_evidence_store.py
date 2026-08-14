"""Process-local, append-only EvidenceStore adapter."""

from uuid import UUID

from packages.domains.evidence.models import Evidence


class InMemoryEvidenceStore:
    """Process-local EvidenceStore adapter. Not durable across restarts.

    Process-local only: no database, no filesystem persistence, no
    serialization layer, no async behavior, no event bus, no dependency on
    DatasetService, DatasetProfiler, or SemanticTyper. Construction is cheap
    and carries no global state — callers own their own instance.
    """

    def __init__(self) -> None:
        # A single ordered list per dataset preserves insertion order and keeps
        # dataset-level evidence (column_name is None) together with column
        # evidence for the same dataset. Reads use ``.get`` so that empty
        # entries are never created as a side effect of querying a missing key.
        self._by_dataset: dict[UUID, list[Evidence]] = {}

    def record(self, evidence: Evidence) -> None:
        """Append one Evidence item. Never overwrites or removes existing Evidence."""
        self._by_dataset.setdefault(evidence.dataset_id, []).append(evidence)

    def for_dataset(self, dataset_id: UUID) -> tuple[Evidence, ...]:
        """Return all Evidence for a dataset, across every analysis run."""
        return tuple(self._by_dataset.get(dataset_id, ()))

    def for_column(self, dataset_id: UUID, column_name: str) -> tuple[Evidence, ...]:
        """Return all Evidence for one column of a dataset, across every run."""
        return tuple(
            item
            for item in self._by_dataset.get(dataset_id, ())
            if item.column_name == column_name
        )
