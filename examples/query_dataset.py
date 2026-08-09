"""Demonstrate querying a CSV dataset with Athena AI.

Usage:
    uv run python examples/query_dataset.py
    uv run python examples/query_dataset.py datasets/sample/CSV/TxnLevel.csv

The example automatically loads the first CSV found under
``datasets/sample/CSV/`` when no path is supplied.

The dataset is registered in DuckDB as ``dataset`` and queried using:

    SELECT *
    FROM dataset
    LIMIT 10;
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

DATASETS_DIRECTORY = Path("datasets")
CSV_DIRECTORY = DATASETS_DIRECTORY / "sample" / "CSV"

SQL_QUERY = """
SELECT *
FROM dataset
LIMIT 10
""".strip()

if TYPE_CHECKING:
    from packages.query.models import QueryResult


def parse_reference() -> str | None:
    """Parse the optional CSV reference from the command line."""
    parser = argparse.ArgumentParser(
        description="Query a CSV dataset using Athena AI."
    )
    parser.add_argument(
        "reference",
        nargs="?",
        help="CSV path under datasets/sample/CSV.",
    )

    arguments = parser.parse_args()
    return cast(str | None, arguments.reference)


def discover_first_csv(project_root: Path) -> str:
    """Discover the first CSV file under datasets/sample/CSV."""
    csv_directory = project_root / CSV_DIRECTORY

    if not csv_directory.is_dir():
        raise FileNotFoundError(
            f"CSV dataset directory does not exist: {csv_directory}"
        )

    csv_files = sorted(
        (
            path
            for path in csv_directory.rglob("*")
            if path.is_file() and path.suffix.lower() == ".csv"
        ),
        key=lambda path: path.as_posix(),
    )

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files were found under: {csv_directory}"
        )

    datasets_root = (project_root / DATASETS_DIRECTORY).resolve()

    return csv_files[0].resolve().relative_to(datasets_root).as_posix()


def resolve_reference(project_root: Path, reference: str) -> str:
    """Convert a user-supplied CSV path into a storage reference."""
    candidate = Path(reference)

    if candidate.is_absolute():
        raise ValueError(
            "Dataset reference must be relative to the repository root."
        )

    datasets_root = (project_root / DATASETS_DIRECTORY).resolve()
    resolved = (project_root / candidate).resolve()
    csv_directory = (project_root / CSV_DIRECTORY).resolve()

    try:
        resolved.relative_to(csv_directory)
    except ValueError as error:
        raise ValueError(
            f"Dataset reference must be located under "
            f"'{CSV_DIRECTORY.as_posix()}'."
        ) from error

    if not resolved.is_file():
        raise FileNotFoundError(
            f"Dataset file does not exist: {reference}"
        )

    if resolved.suffix.lower() != ".csv":
        raise ValueError(
            f"Reference does not point to a CSV file: {reference}"
        )

    return resolved.relative_to(datasets_root).as_posix()


def display_result(
    reference: str,
    query_result: QueryResult,
) -> None:
    """Display query metadata and the query result."""
    print("=" * 72)
    print("ATHENA AI")
    print("DuckDB Query Example")
    print("=" * 72)

    print("\nDataset")
    print("-" * 72)
    print(f"Reference          : {reference}")

    print("\nSQL Query")
    print("-" * 72)
    print(query_result.sql)

    print("\nQuery Result")
    print("-" * 72)
    print(f"Rows               : {query_result.row_count:,}")
    print(f"Columns            : {query_result.column_count:,}")

    print("\nPreview")
    print("-" * 72)
    print(query_result.dataframe)

    print("\nExecution")
    print("-" * 72)
    print(
        f"Execution time     : "
        f"{query_result.execution_time_ms:.4f} ms"
    )
    print("Status             : Completed successfully")


def main() -> int:
    """Run the DuckDB query example."""
    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from packages.loaders.csv import CSVLoader
    from packages.query.duckdb import DuckDBQueryEngine
    from packages.shared.exceptions import (
        CSVLoadError,
        InvalidStorageReferenceError,
        QueryExecutionError,
        StorageAssetNotFoundError,
    )
    from packages.storage.blob.local import LocalStorageProvider

    try:
        supplied_reference = parse_reference()

        reference = (
            resolve_reference(project_root, supplied_reference)
            if supplied_reference
            else discover_first_csv(project_root)
        )

        storage_root = project_root / DATASETS_DIRECTORY
        storage_provider = LocalStorageProvider(storage_root)
        loader = CSVLoader(storage_provider)

        load_result = loader.load(reference)

        query_engine = DuckDBQueryEngine()
        query_result = query_engine.execute(load_result, SQL_QUERY)

        display_result(reference, query_result)

        return 0

    except (
        CSVLoadError,
        FileNotFoundError,
        InvalidStorageReferenceError,
        QueryExecutionError,
        StorageAssetNotFoundError,
        ValueError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())