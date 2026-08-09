"""Benchmark Athena AI CSV and Excel loading performance.

Usage:
    uv run python examples/benchmark_loading.py

Run a custom number of iterations:

    uv run python examples/benchmark_loading.py --iterations 3

Benchmark specific datasets:

    uv run python examples/benchmark_loading.py \
        datasets/sample/csv/TxnLevel.csv \
        datasets/sample/excel/TxnLevel.xlsx

The benchmark reports minimum, maximum, and average loading time,
rows per second, and source MB per second.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

DATASETS_DIRECTORY = Path("datasets")

DEFAULT_DATASETS = (
    DATASETS_DIRECTORY / "sample" / "csv" / "TxnLevel.csv",
    DATASETS_DIRECTORY / "sample" / "excel" / "TxnLevel.xlsx",
)

DEFAULT_ITERATIONS = 3

if TYPE_CHECKING:
    from packages.interfaces.storage import StorageProvider
    from packages.loaders.csv import CSVLoader
    from packages.loaders.excel import ExcelLoader
    from packages.loaders.models import TabularLoadResult

    Loader = CSVLoader | ExcelLoader


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Store benchmark measurements for one dataset."""

    reference: str
    extension: str
    size_bytes: int
    row_count: int
    column_count: int
    iterations: int
    minimum_seconds: float
    maximum_seconds: float
    average_seconds: float

    @property
    def rows_per_second(self) -> float:
        """Return the average number of loaded rows per second."""
        if self.average_seconds == 0:
            return 0.0

        return self.row_count / self.average_seconds

    @property
    def megabytes_per_second(self) -> float:
        """Return the average source throughput in decimal MB/s."""
        if self.average_seconds == 0:
            return 0.0

        return (self.size_bytes / 1_000_000) / self.average_seconds


def parse_arguments() -> argparse.Namespace:
    """Parse benchmark command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark Athena AI CSV and Excel loading."
    )
    parser.add_argument(
        "references",
        nargs="*",
        help=(
            "Dataset paths relative to the repository root. "
            "Defaults to TxnLevel CSV and Excel datasets."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=(
            "Number of times to load each dataset "
            f"(default: {DEFAULT_ITERATIONS})."
        ),
    )

    return parser.parse_args()


def validate_iterations(iterations: int) -> None:
    """Validate the requested benchmark iteration count."""
    if iterations < 1:
        raise ValueError("Iterations must be at least 1.")


def resolve_reference(project_root: Path, reference: str) -> str:
    """Resolve a dataset path into a storage reference."""
    candidate = Path(reference)

    if candidate.is_absolute():
        raise ValueError(
            "Dataset references must be relative to the repository root."
        )

    datasets_root = (project_root / DATASETS_DIRECTORY).resolve()
    resolved = (project_root / candidate).resolve()

    try:
        resolved.relative_to(datasets_root)
    except ValueError as error:
        raise ValueError(
            "Dataset references must be located under "
            f"'{DATASETS_DIRECTORY.as_posix()}'."
        ) from error

    if not resolved.is_file():
        raise FileNotFoundError(
            f"Dataset file does not exist: {reference}"
        )

    extension = resolved.suffix.lower()

    if extension not in {".csv", ".xls", ".xlsx"}:
        raise ValueError(
            f"Unsupported dataset format '{extension}' for: {reference}"
        )

    return resolved.relative_to(datasets_root).as_posix()


def get_loader(
    extension: str,
    storage_provider: StorageProvider,
) -> Loader:
    """Create the appropriate loader for a dataset extension."""
    from packages.loaders.csv import CSVLoader
    from packages.loaders.excel import ExcelLoader

    if extension == ".csv":
        return CSVLoader(storage_provider)

    if extension in {".xls", ".xlsx"}:
        return ExcelLoader(storage_provider)

    raise ValueError(f"Unsupported dataset extension: {extension}")


def benchmark_dataset(
    project_root: Path,
    reference: str,
    iterations: int,
) -> BenchmarkResult:
    """Benchmark repeated loading of one dataset."""
    from packages.storage.blob.local import LocalStorageProvider

    datasets_root = project_root / DATASETS_DIRECTORY
    storage_provider = LocalStorageProvider(datasets_root)

    dataset_path = datasets_root / reference
    extension = dataset_path.suffix.lower()

    loader = get_loader(extension, storage_provider)

    timings: list[float] = []
    load_result: TabularLoadResult | None = None

    for _ in range(iterations):
        started = time.perf_counter()
        result = loader.load(reference)
        elapsed = time.perf_counter() - started

        timings.append(elapsed)
        load_result = result

    if load_result is None:
        raise RuntimeError("Benchmark completed without a load result.")

    return BenchmarkResult(
        reference=reference,
        extension=load_result.asset.extension,
        size_bytes=load_result.asset.size_bytes,
        row_count=load_result.row_count,
        column_count=load_result.column_count,
        iterations=iterations,
        minimum_seconds=min(timings),
        maximum_seconds=max(timings),
        average_seconds=statistics.fmean(timings),
    )


def format_number(value: float) -> str:
    """Format a floating-point measurement for console output."""
    return f"{value:,.2f}"


def display_result(result: BenchmarkResult) -> None:
    """Display benchmark results for one dataset."""
    print(f"\nDataset             : {result.reference}")
    print(f"Format              : {result.extension}")
    print(f"Size                : {result.size_bytes:,} bytes")
    print(f"Rows                : {result.row_count:,}")
    print(f"Columns             : {result.column_count:,}")
    print(f"Iterations          : {result.iterations}")
    print(
        f"Minimum load time   : "
        f"{result.minimum_seconds:.4f} seconds"
    )
    print(
        f"Maximum load time   : "
        f"{result.maximum_seconds:.4f} seconds"
    )
    print(
        f"Average load time   : "
        f"{result.average_seconds:.4f} seconds"
    )
    print(
        f"Rows / second       : "
        f"{format_number(result.rows_per_second)}"
    )
    print(
        f"Source MB / second  : "
        f"{format_number(result.megabytes_per_second)}"
    )


def main() -> int:
    """Run the loading benchmark."""
    project_root = Path(__file__).resolve().parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from packages.shared.exceptions import (
            CSVLoadError,
            ExcelLoadError,
            InvalidStorageReferenceError,
            StorageAssetNotFoundError,
        )

        arguments = parse_arguments()
        validate_iterations(arguments.iterations)

        references = (
            [
                resolve_reference(project_root, reference)
                for reference in arguments.references
            ]
            if arguments.references
            else [
                resolve_reference(project_root, reference.as_posix())
                for reference in DEFAULT_DATASETS
            ]
        )

        print("=" * 72)
        print("ATHENA AI")
        print("Loading Performance Benchmark")
        print("=" * 72)
        print(f"\nIterations per dataset: {arguments.iterations}")

        benchmark_started = time.perf_counter()
        results: list[BenchmarkResult] = []

        for reference in references:
            print(f"\nBenchmarking: {reference}")

            result = benchmark_dataset(
                project_root,
                reference,
                arguments.iterations,
            )
            results.append(result)

        for result in results:
            display_result(result)

        total_elapsed = time.perf_counter() - benchmark_started

        print("\nBenchmark Summary")
        print("-" * 72)

        for result in results:
            print(
                f"{result.reference:<40} "
                f"{result.average_seconds:.4f} s average"
            )

        print(f"\nTotal benchmark time : {total_elapsed:.4f} seconds")
        print("Status               : Completed successfully")

        return 0

    except (
        CSVLoadError,
        ExcelLoadError,
        FileNotFoundError,
        InvalidStorageReferenceError,
        StorageAssetNotFoundError,
        ValueError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())