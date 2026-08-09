"""Demonstrate dataset profiling with Athena AI.

Usage:
    uv run python examples/profile_dataset.py
    uv run python examples/profile_dataset.py datasets/sample/CSV/TxnLevel.csv

When no path is supplied, the first CSV file found under
``datasets/sample/CSV/`` is loaded and profiled automatically.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, cast

DATASETS_DIRECTORY = Path("datasets")
CSV_DIRECTORY = DATASETS_DIRECTORY / "sample" / "CSV"

if TYPE_CHECKING:
    from packages.profiling.models import ProfileResult


def parse_reference() -> str | None:
    """Parse the optional dataset reference from the command line."""
    parser = argparse.ArgumentParser(
        description="Profile a dataset using Athena AI."
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
    """Convert a user-supplied dataset path into a storage reference."""
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


def display_profile(
    result: ProfileResult,
    elapsed_seconds: float,
) -> None:
    """Display the dataset profile."""
    summary = result.summary
    quality = result.data_quality
    recommendations = result.recommendations

    print("=" * 72)
    print("ATHENA AI")
    print("Dataset Profiling Example")
    print("=" * 72)

    print("\nDataset")
    print("-" * 72)
    print(f"Reference          : {summary.reference}")
    print(f"Name               : {summary.name}")
    print(f"Rows               : {summary.row_count:,}")
    print(f"Columns            : {summary.column_count:,}")
    print(
        f"Estimated size     : "
        f"{summary.estimated_size_bytes:,} bytes"
    )

    print("\nColumn Profiles")
    print("-" * 72)

    for column_profile in result.columns:
        print(f"Column             : {column_profile.name}")
        print(f"Type               : {column_profile.data_type}")
        print(f"Nulls              : {column_profile.null_count:,}")
        print(
            f"Null %             : "
            f"{column_profile.null_percentage:.2f}%"
        )
        print(
            f"Distinct           : "
            f"{column_profile.distinct_count:,}"
        )
        print(
            f"Distinct %         : "
            f"{column_profile.distinct_percentage:.2f}%"
        )
        print()

    print("Data Quality")
    print("-" * 72)
    print(f"Total cells        : {quality.total_cell_count:,}")
    print(f"Null cells         : {quality.null_cell_count:,}")
    print(f"Null %             : {quality.null_percentage:.2f}%")
    print(f"Duplicate rows     : {quality.duplicate_row_count:,}")
    print(
        f"Duplicate %        : "
        f"{quality.duplicate_row_percentage:.2f}%"
    )
    print(f"Empty columns      : {quality.empty_column_count:,}")

    print("\nRecommendations")
    print("-" * 72)

    print("Potential primary keys")
    if recommendations.potential_primary_keys:
        for column_name in recommendations.potential_primary_keys:
            print(f"  - {column_name}")
    else:
        print("  - None identified")

    print("Identifier columns")
    if recommendations.identifier_columns:
        for column_name in recommendations.identifier_columns:
            print(f"  - {column_name}")
    else:
        print("  - None identified")

    print("Categorical columns")
    if recommendations.categorical_columns:
        for column_name in recommendations.categorical_columns:
            print(f"  - {column_name}")
    else:
        print("  - None identified")

    print("Numeric measures")
    if recommendations.numeric_measures:
        for column_name in recommendations.numeric_measures:
            print(f"  - {column_name}")
    else:
        print("  - None identified")

    print("Date dimensions")
    if recommendations.date_dimensions:
        for column_name in recommendations.date_dimensions:
            print(f"  - {column_name}")
    else:
        print("  - None identified")

    print("\nExecution")
    print("-" * 72)
    print(f"Profiling time      : {elapsed_seconds:.4f} seconds")
    print("Status              : Completed successfully")


def main() -> int:
    """Run the dataset profiling example."""
    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from packages.loaders.csv import CSVLoader
    from packages.profiling.profiler import DatasetProfiler
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

        load_started = time.perf_counter()
        load_result = loader.load(reference)
        load_elapsed_seconds = time.perf_counter() - load_started

        profiler = DatasetProfiler()

        profile_started = time.perf_counter()
        profile_result = profiler.profile(load_result)
        profile_elapsed_seconds = time.perf_counter() - profile_started

        display_profile(profile_result, profile_elapsed_seconds)

        print(
            f"\nLoad time           : "
            f"{load_elapsed_seconds:.4f} seconds"
        )

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