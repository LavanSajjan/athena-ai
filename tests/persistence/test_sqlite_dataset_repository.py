"""Tests for durable SQLite Dataset persistence."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.persistence.sqlite_dataset_repository import SQLiteDatasetRepository


def _dataset(
    *,
    status: DatasetStatus = DatasetStatus.REGISTERED,
    sha256: str | None = "a" * 64,
    created_at: datetime | None = None,
) -> Dataset:
    return Dataset(
        id=uuid4(),
        provider_id="local",
        reference="unusual/../opaque reference.csv",
        name="sales",
        source_type="csv",
        asset_uri="file:///descriptive/sales.csv",
        size_bytes=24,
        created_at=created_at or datetime(2026, 8, 12, 9, 30, tzinfo=UTC),
        status=status,
        sha256=sha256,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[SQLiteDatasetRepository]:
    """Provide an initialized repository with an isolated catalog."""
    instance = SQLiteDatasetRepository(tmp_path / "catalog.sqlite3")
    instance.initialize()
    yield instance
    instance.close()


@pytest.mark.parametrize("status", list(DatasetStatus))
@pytest.mark.parametrize("sha256", ["b" * 64, None])
def test_repository_round_trips_every_dataset_field(
    repository: SQLiteDatasetRepository,
    status: DatasetStatus,
    sha256: str | None,
) -> None:
    """Persistence should preserve Dataset values without reference interpretation."""
    created_at = datetime(2026, 8, 12, 15, 0, tzinfo=UTC)
    dataset = _dataset(status=status, sha256=sha256, created_at=created_at)

    repository.add(dataset)

    assert repository.get(dataset.id) == dataset


def test_repository_normalizes_timezone_aware_created_at(
    repository: SQLiteDatasetRepository,
) -> None:
    """Stored timestamps should preserve their instant as UTC-aware datetimes."""
    offset_timezone = timezone(timedelta(hours=5, minutes=30))
    dataset = _dataset(created_at=datetime(2026, 8, 12, 20, 30, tzinfo=offset_timezone))
    repository.add(dataset)

    restored = repository.get(dataset.id)

    assert restored is not None
    assert restored.created_at == datetime(2026, 8, 12, 15, 0, tzinfo=UTC)
    assert restored.created_at.tzinfo is not None


def test_repository_returns_none_for_missing_dataset(repository: SQLiteDatasetRepository) -> None:
    """Unknown UUIDs should not produce a Dataset."""
    assert repository.get(uuid4()) is None


def test_repository_lists_datasets_in_deterministic_order(
    repository: SQLiteDatasetRepository,
) -> None:
    """Listings should be sorted by created time and UUID rather than insertion order."""
    created_at = datetime(2026, 8, 12, 10, 0, tzinfo=UTC)
    later = _dataset(created_at=created_at).model_copy(update={"id": UUID(int=2)})
    earlier = _dataset(created_at=created_at).model_copy(update={"id": UUID(int=1)})
    repository.add(later)
    repository.add(earlier)

    assert repository.list() == [earlier, later]


def test_initialize_creates_a_fresh_database_and_is_idempotent(tmp_path: Path) -> None:
    """Initialization should create and safely re-open the versioned schema."""
    database_path = tmp_path / "nested" / "catalog.sqlite3"
    repository = SQLiteDatasetRepository(database_path)

    repository.initialize()
    repository.initialize()

    assert database_path.is_file()
    assert repository.list() == []
    repository.close()


def test_repository_preserves_registrations_across_restart(tmp_path: Path) -> None:
    """A new repository instance should recover a prior registration by UUID."""
    database_path = tmp_path / "catalog.sqlite3"
    dataset = _dataset()
    first = SQLiteDatasetRepository(database_path)
    first.initialize()
    first.add(dataset)
    first.close()

    restarted = SQLiteDatasetRepository(database_path)
    restarted.initialize()

    assert restarted.get(dataset.id) == dataset
    restarted.close()
