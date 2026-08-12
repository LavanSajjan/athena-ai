"""Versioned SQLite schema migrations for Athena persistence."""

import sqlite3
from collections.abc import Callable

Migration = tuple[int, Callable[[sqlite3.Connection], None]]


def _create_datasets_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE datasets (
            id TEXT PRIMARY KEY NOT NULL,
            provider_id TEXT NOT NULL,
            reference TEXT NOT NULL,
            name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            asset_uri TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('new', 'registered', 'profiled', 'validated', 'ready', 'archived')
            ),
            sha256 TEXT
        )
        """
    )


MIGRATIONS: tuple[Migration, ...] = ((1, _create_datasets_table),)


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply unapplied migrations in one transactional, versioned sequence."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied_versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for version, migration in MIGRATIONS:
            if version not in applied_versions:
                migration(connection)
                connection.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
