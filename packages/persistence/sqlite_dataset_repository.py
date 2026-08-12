"""SQLite implementation of the DatasetRepository port."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import UUID

from packages.domains.dataset.enums import DatasetStatus
from packages.domains.dataset.models import Dataset
from packages.persistence.migrations import apply_migrations


class SQLiteDatasetRepository:
    """Persist Dataset aggregates in a local SQLite catalog."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        """Open the catalog and bring its schema to the latest version."""
        with self._lock:
            if self._connection is not None:
                return

            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.database_path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            try:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA busy_timeout = 5000")
                apply_migrations(connection)
            except Exception:
                connection.close()
                raise
            self._connection = connection

    def close(self) -> None:
        """Close the open SQLite connection, if any."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def add(self, dataset: Dataset) -> None:
        """Insert a registered dataset without interpreting its reference."""
        with self._lock:
            connection = self._require_connection()
            with connection:
                connection.execute(
                    """
                    INSERT INTO datasets (
                        id, provider_id, reference, name, source_type, asset_uri,
                        size_bytes, created_at, status, sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(dataset.id),
                        dataset.provider_id,
                        dataset.reference,
                        dataset.name,
                        dataset.source_type,
                        dataset.asset_uri,
                        dataset.size_bytes,
                        self._serialize_created_at(dataset.created_at),
                        dataset.status.value,
                        dataset.sha256,
                    ),
                )

    def get(self, dataset_id: UUID) -> Dataset | None:
        """Return a dataset by its UUID, if it exists."""
        with self._lock:
            connection = self._require_connection()
            row = connection.execute(
                "SELECT * FROM datasets WHERE id = ?", (str(dataset_id),)
            ).fetchone()
            return self._to_dataset(row) if row is not None else None

    def list(self) -> list[Dataset]:
        """Return datasets in stable creation and UUID order."""
        with self._lock:
            connection = self._require_connection()
            rows = connection.execute(
                "SELECT * FROM datasets ORDER BY created_at ASC, id ASC"
            ).fetchall()
            return [self._to_dataset(row) for row in rows]

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("SQLiteDatasetRepository must be initialized before use.")
        return self._connection

    def _to_dataset(self, row: sqlite3.Row) -> Dataset:
        return Dataset(
            id=UUID(row["id"]),
            provider_id=row["provider_id"],
            reference=row["reference"],
            name=row["name"],
            source_type=row["source_type"],
            asset_uri=row["asset_uri"],
            size_bytes=row["size_bytes"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=DatasetStatus(row["status"]),
            sha256=row["sha256"],
        )

    def _serialize_created_at(self, created_at: datetime) -> str:
        if created_at.tzinfo is None:
            raise ValueError("Dataset.created_at must be timezone-aware.")
        return created_at.astimezone(UTC).isoformat()
