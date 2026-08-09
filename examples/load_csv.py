"""Demonstrate loading a CSV dataset with Athena AI.

Usage:
    uv run python examples/load_csv.py
    uv run python examples/load_csv.py datasets/sample/CSV/Automobile.csv

When no path is supplied, the first CSV file found under
``datasets/sample/CSV/`` is loaded automatically.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

DATASETS_DIRECTORY = Path("datasets")
CSV_DIRECTORY = DATASETS_DIRECTORY / "sample" / "CSV"
PREVIEW_ROWS = 5

if TYPE_CHECKING:
    from packages.loaders.models import CSVLoadResult


def parse_reference() -> str | None:
    """Parse the optional CSV reference from the command line."""
    parser = argparse.ArgumentParser(
        description="Load a CSV dataset using Athena AI."
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
    """Convert a user-supplied CSV path into a storage-relative reference."""
    candidate = Path(reference)

    if candidate.is_absolute():
        raise ValueError(
            "CSV reference must be relative to the repository root."
        )

    datasets_root = (project_root / DATASETS_DIRECTORY).resolve()
    resolved = (project_root / candidate).resolve()

    csv_directory = (project_root / CSV_DIRECTORY).resolve()

    try:
        resolved.relative_to(csv_directory)
    except ValueError as error:
        raise ValueError(
            f"CSV reference must be located under "
            f"'{CSV_DIRECTORY.as_posix()}'."
        ) from error

    if not resolved.is_file():
        raise FileNotFoundError(
            f"CSV file does not exist: {reference}"
        )

    if resolved.suffix.lower() != ".csv":
        raise ValueError(
            f"Reference does not point to a CSV file: {reference}"
        )

    return resolved.relative_to(datasets_root).as_posix()


def display_result(
    reference: str,
    result: CSVLoadResult,
    elapsed_seconds: float,
) -> None:
    """Display the loaded dataset metadata and preview."""
    asset = result.asset

    print("=" * 72)
    print("ATHENA AI")
    print("CSV Loader Example")
    print("=" * 72)

    print("\nDataset")
    print("-" * 72)
    print(f"Reference          : {reference}")
    print(f"Name               : {asset.name}")
    print(f"Extension          : {asset.extension}")
    print(f"Size               : {asset.size_bytes:,} bytes")
    print(f"SHA-256            : {asset.sha256}")

    print("\nLoad Result")
    print("-" * 72)
    print(f"Rows               : {result.row_count:,}")
    print(f"Columns            : {result.column_count:,}")
    print(f"Estimated size     : {result.estimated_size_bytes:,} bytes")

    print("\nColumn Names")
    print("-" * 72)

    for column in result.column_names:
        print(f"- {column}")

    print("\nPreview")
    print("-" * 72)
    print(result.dataframe.head(PREVIEW_ROWS))

    print("\nExecution")
    print("-" * 72)
    print(f"Execution time     : {elapsed_seconds:.4f} seconds")
    print("Status             : Completed successfully")


def main() -> int:
    """Run the CSV loading example."""
    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from packages.loaders.csv import CSVLoader
    from packages.shared.exceptions import (
        CSVLoadError,
        InvalidStorageReferenceError,
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

        started = time.perf_counter()
        result = loader.load(reference)
        elapsed_seconds = time.perf_counter() - started

        display_result(reference, result, elapsed_seconds)

        return 0

    except (
        CSVLoadError,
        FileNotFoundError,
        InvalidStorageReferenceError,
        StorageAssetNotFoundError,
        ValueError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())