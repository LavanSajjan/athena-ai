"""Models used by dataset loaders."""

from collections.abc import Mapping
from dataclasses import dataclass

import polars as pl

from packages.models.domain.storage import StorageAsset


@dataclass(frozen=True, slots=True)
class CSVLoadOptions:
    """Configuration applied when parsing a CSV asset with Polars."""

    has_header: bool = True
    separator: str = ","
    encoding: str = "utf8"
    null_values: tuple[str, ...] | None = None
    schema_overrides: Mapping[str, pl.DataType | type[pl.DataType]] | None = None
    infer_schema_length: int | None = None


@dataclass(frozen=True, slots=True)
class TabularLoadResult:
    """Parsed tabular data and metadata describing its storage source."""

    asset: StorageAsset
    dataframe: pl.DataFrame
    row_count: int
    column_count: int
    column_names: list[str]
    estimated_size_bytes: int


@dataclass(frozen=True, slots=True)
class CSVLoadResult(TabularLoadResult):
    """Backward-compatible result type returned by :class:`CSVLoader`."""


@dataclass(frozen=True, slots=True)
class ExcelLoadOptions:
    """Configuration applied when parsing an Excel worksheet with Polars."""

    worksheet: str | int | None = None
    has_header: bool = True
    schema_overrides: Mapping[str, pl.DataType | type[pl.DataType]] | None = None
    infer_schema_length: int | None = 100
