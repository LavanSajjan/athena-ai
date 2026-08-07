"""Provider-neutral Excel loading implemented with Polars."""

from typing import Any

import fastexcel
import polars as pl

from packages.interfaces.storage import StorageProvider
from packages.loaders.models import ExcelLoadOptions, TabularLoadResult
from packages.shared.exceptions import ExcelLoadError


class ExcelLoader:
    """Load Excel worksheets supplied by a storage provider into Polars dataframes."""

    def __init__(self, storage_provider: StorageProvider) -> None:
        """Initialize the loader with the storage provider used to access assets."""
        self.storage_provider = storage_provider

    def load(
        self,
        reference: str,
        options: ExcelLoadOptions | None = None,
    ) -> TabularLoadResult:
        """Load an Excel worksheet and return parsed data with source metadata."""
        load_options = options or ExcelLoadOptions()
        self._validate_options(load_options)

        asset = self.storage_provider.describe(reference)
        source = self.storage_provider.open_binary(reference)

        try:
            with source:
                dataframe = pl.read_excel(source, **self._read_options(load_options))
        except (
            fastexcel.CalamineError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
            pl.exceptions.PolarsError,
        ) as error:
            raise ExcelLoadError(f"Unable to load Excel asset: {reference}") from error

        if not isinstance(dataframe, pl.DataFrame):
            raise ExcelLoadError("Excel worksheet selection must resolve to one worksheet.")

        return TabularLoadResult(
            asset=asset,
            dataframe=dataframe,
            row_count=dataframe.height,
            column_count=dataframe.width,
            column_names=dataframe.columns,
            estimated_size_bytes=int(dataframe.estimated_size()),
        )

    def _read_options(self, options: ExcelLoadOptions) -> dict[str, Any]:
        """Translate Athena options into Polars Excel reader options."""
        read_options: dict[str, Any] = {
            "has_header": options.has_header,
            "schema_overrides": options.schema_overrides,
            "infer_schema_length": options.infer_schema_length,
        }

        if isinstance(options.worksheet, str):
            read_options["sheet_name"] = options.worksheet
        elif isinstance(options.worksheet, int):
            read_options["sheet_id"] = options.worksheet

        return read_options

    def _validate_options(self, options: ExcelLoadOptions) -> None:
        """Validate loader configuration before invoking the Polars parser."""
        if isinstance(options.worksheet, bool) or (
            isinstance(options.worksheet, int) and options.worksheet < 1
        ):
            raise ExcelLoadError("Excel worksheet IDs must be positive integers.")

        if isinstance(options.worksheet, str) and not options.worksheet.strip():
            raise ExcelLoadError("Excel worksheet names must not be empty.")

        if options.infer_schema_length is not None and options.infer_schema_length <= 0:
            raise ExcelLoadError("Excel schema inference length must be greater than zero.")
