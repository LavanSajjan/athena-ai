"""Provider-neutral CSV loading implemented with Polars."""

import polars as pl

from packages.interfaces.storage import StorageProvider
from packages.loaders.models import CSVLoadOptions, CSVLoadResult
from packages.shared.exceptions import CSVLoadError


class CSVLoader:
    """Load CSV assets supplied by a storage provider into Polars dataframes."""

    def __init__(self, storage_provider: StorageProvider) -> None:
        """Initialize the loader with the storage provider used to access assets."""
        self.storage_provider = storage_provider

    def load(
        self,
        reference: str,
        options: CSVLoadOptions | None = None,
    ) -> CSVLoadResult:
        """Load ``reference`` and return parsed data with source metadata."""
        load_options = options or CSVLoadOptions()
        self._validate_options(load_options)

        asset = self.storage_provider.describe(reference)
        source = self.storage_provider.open_binary(reference)

        try:
            with source:
                dataframe = pl.read_csv(
                    source,
                    has_header=load_options.has_header,
                    separator=load_options.separator,
                    encoding=load_options.encoding,
                    null_values=load_options.null_values,
                    schema_overrides=load_options.schema_overrides,
                    infer_schema_length=load_options.infer_schema_length,
                )
        except (pl.exceptions.PolarsError, LookupError, UnicodeDecodeError, ValueError) as error:
            raise CSVLoadError(f"Unable to load CSV asset: {reference}") from error

        estimated_size = dataframe.estimated_size()

        return CSVLoadResult(
            asset=asset,
            dataframe=dataframe,
            row_count=dataframe.height,
            column_count=dataframe.width,
            column_names=dataframe.columns,
            estimated_size_bytes=int(estimated_size),
        )

    def _validate_options(self, options: CSVLoadOptions) -> None:
        """Validate loader configuration before invoking the Polars parser."""
        if len(options.separator) != 1:
            raise CSVLoadError("CSV separator must contain exactly one character.")

        if options.infer_schema_length is not None and options.infer_schema_length <= 0:
            raise CSVLoadError("CSV schema inference length must be greater than zero.")
