"""Tests for provider-neutral CSV ingestion with Polars."""

from io import BytesIO
from typing import BinaryIO

import polars as pl
import pytest

from packages.loaders.csv import CSVLoader
from packages.loaders.models import CSVLoadOptions
from packages.models.domain.storage import StorageAsset
from packages.shared.exceptions import CSVLoadError, StorageAssetNotFoundError


class TrackingBinaryStream(BytesIO):
    """Track whether the loader closes a provider-owned binary stream."""

    def __init__(self, contents: bytes) -> None:
        """Initialize the stream with CSV content."""
        super().__init__(contents)
        self.was_closed = False

    def close(self) -> None:
        """Record stream closure before releasing the in-memory buffer."""
        self.was_closed = True
        super().close()


class InMemoryStorageProvider:
    """Provide storage assets from in-memory binary content for loader tests."""

    def __init__(self, reference: str, contents: bytes) -> None:
        """Initialize provider metadata and content for one CSV asset."""
        self.reference = reference
        self.contents = contents
        self.describe_calls: list[str] = []
        self.open_calls: list[str] = []
        self.last_stream: TrackingBinaryStream | None = None

    def describe(self, reference: str) -> StorageAsset:
        """Return deterministic metadata for the configured asset."""
        self.describe_calls.append(reference)
        return StorageAsset(
            reference=reference,
            name="records",
            extension="csv",
            uri=f"memory://{reference}",
            size_bytes=len(self.contents),
            sha256="a" * 64,
        )

    def open_binary(self, reference: str) -> BinaryIO:
        """Return a fresh binary stream containing the configured CSV content."""
        self.open_calls.append(reference)
        self.last_stream = TrackingBinaryStream(self.contents)
        return self.last_stream


def test_load_returns_parsed_dataframe_and_asset_metadata() -> None:
    """The loader should parse provider content and retain its source metadata."""
    provider = InMemoryStorageProvider("sample/records.csv", b"id,name\n1,Athena\n2,Zeus\n")
    loader = CSVLoader(provider)

    result = loader.load("sample/records.csv")

    assert provider.describe_calls == ["sample/records.csv"]
    assert provider.open_calls == ["sample/records.csv"]
    assert result.asset.uri == "memory://sample/records.csv"
    assert result.dataframe.to_dicts() == [
        {"id": 1, "name": "Athena"},
        {"id": 2, "name": "Zeus"},
    ]
    assert result.row_count == 2
    assert result.column_count == 2
    assert result.column_names == ["id", "name"]
    assert result.estimated_size_bytes == result.dataframe.estimated_size()
    assert provider.last_stream is not None
    assert provider.last_stream.was_closed


def test_load_supports_csv_options() -> None:
    """The loader should map supported options directly to Polars parsing behavior."""
    provider = InMemoryStorageProvider("sample/records.csv", b"id;name\n1;NULL\n2;Athena\n")
    loader = CSVLoader(provider)
    options = CSVLoadOptions(
        separator=";",
        null_values=("NULL",),
        schema_overrides={"id": pl.Int64},
        infer_schema_length=10,
    )

    result = loader.load("sample/records.csv", options)

    assert result.dataframe.schema == {"id": pl.Int64, "name": pl.String}
    assert result.dataframe["name"].to_list() == [None, "Athena"]


def test_load_supports_headerless_csv_content() -> None:
    """The loader should support CSV assets whose first row is data."""
    provider = InMemoryStorageProvider("sample/headerless.csv", b"1,Athena\n2,Zeus\n")
    loader = CSVLoader(provider)

    result = loader.load("sample/headerless.csv", CSVLoadOptions(has_header=False))

    assert result.column_names == ["column_1", "column_2"]
    assert result.dataframe.to_dicts() == [
        {"column_1": 1, "column_2": "Athena"},
        {"column_1": 2, "column_2": "Zeus"},
    ]


def test_load_supports_utf8_unicode_content() -> None:
    """The loader should preserve UTF-8 text from provider-backed CSV content."""
    contents = "city,label\nMünchen,Grüße\n東京,こんにちは\n".encode()
    provider = InMemoryStorageProvider("sample/unicode.csv", contents)
    loader = CSVLoader(provider)

    result = loader.load("sample/unicode.csv")

    assert result.dataframe.to_dicts() == [
        {"city": "München", "label": "Grüße"},
        {"city": "東京", "label": "こんにちは"},
    ]


def test_load_handles_one_hundred_thousand_rows() -> None:
    """The loader should parse a representative large CSV without changing behavior."""
    rows = "".join(f"{row},value-{row}\n" for row in range(100_000))
    provider = InMemoryStorageProvider("sample/large.csv", f"id,value\n{rows}".encode())
    loader = CSVLoader(provider)

    result = loader.load("sample/large.csv")

    assert result.row_count == 100_000
    assert result.column_count == 2
    assert result.dataframe.row(99_999) == (99_999, "value-99999")
    assert result.estimated_size_bytes > 0


def test_load_propagates_storage_errors_unchanged() -> None:
    """Provider-owned failures must not be wrapped by the CSV loader."""

    class MissingStorageProvider:
        """Represent a provider that cannot describe an asset."""

        def describe(self, reference: str) -> StorageAsset:
            """Raise the provider-owned missing-asset error."""
            raise StorageAssetNotFoundError(reference)

        def open_binary(self, reference: str) -> BinaryIO:
            """Provide protocol compatibility for this failing test provider."""
            return BytesIO()

    loader = CSVLoader(MissingStorageProvider())

    with pytest.raises(StorageAssetNotFoundError):
        loader.load("sample/missing.csv")


def test_load_wraps_malformed_csv_errors() -> None:
    """Polars parser failures should be surfaced as loader-owned exceptions."""
    provider = InMemoryStorageProvider("sample/broken.csv", b'name,city\nAthena,"Olympus\n')
    loader = CSVLoader(provider)

    with pytest.raises(CSVLoadError) as error:
        loader.load("sample/broken.csv")

    assert isinstance(error.value.__cause__, pl.exceptions.PolarsError)


def test_load_wraps_empty_csv_errors() -> None:
    """Empty CSV assets should fail with a loader-owned parsing exception."""
    provider = InMemoryStorageProvider("sample/empty.csv", b"")
    loader = CSVLoader(provider)

    with pytest.raises(CSVLoadError) as error:
        loader.load("sample/empty.csv")

    assert isinstance(error.value.__cause__, pl.exceptions.PolarsError)


def test_load_wraps_invalid_encoding_errors() -> None:
    """Unsupported parser encodings should produce a loader-owned exception."""
    provider = InMemoryStorageProvider("sample/records.csv", b"id\n1\n")
    loader = CSVLoader(provider)

    with pytest.raises(CSVLoadError):
        loader.load("sample/records.csv", CSVLoadOptions(encoding="not-an-encoding"))


@pytest.mark.parametrize(
    "options",
    [
        CSVLoadOptions(separator=""),
        CSVLoadOptions(separator="::"),
        CSVLoadOptions(infer_schema_length=0),
    ],
)
def test_load_rejects_invalid_options(options: CSVLoadOptions) -> None:
    """Invalid loader-owned options should fail before storage is accessed."""
    provider = InMemoryStorageProvider("sample/records.csv", b"id\n1\n")
    loader = CSVLoader(provider)

    with pytest.raises(CSVLoadError):
        loader.load("sample/records.csv", options)

    assert provider.describe_calls == []
    assert provider.open_calls == []
