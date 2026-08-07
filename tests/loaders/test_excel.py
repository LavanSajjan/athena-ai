"""Tests for provider-neutral Excel ingestion with Polars."""

# ruff: noqa: E501

from io import BytesIO
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile

import polars as pl
import pytest

from packages.loaders.excel import ExcelLoader
from packages.loaders.models import ExcelLoadOptions, TabularLoadResult
from packages.models.domain.storage import StorageAsset
from packages.shared.exceptions import ExcelLoadError, StorageAssetNotFoundError


class TrackingBinaryStream(BytesIO):
    """Track whether the loader closes a provider-owned binary stream."""

    def __init__(self, contents: bytes) -> None:
        super().__init__(contents)
        self.was_closed = False

    def close(self) -> None:
        self.was_closed = True
        super().close()


class InMemoryStorageProvider:
    """Provide an Excel asset from in-memory binary content."""

    def __init__(self, reference: str, contents: bytes) -> None:
        self.reference = reference
        self.contents = contents
        self.describe_calls: list[str] = []
        self.open_calls: list[str] = []
        self.last_stream: TrackingBinaryStream | None = None

    def describe(self, reference: str) -> StorageAsset:
        self.describe_calls.append(reference)
        return StorageAsset(
            reference=reference,
            name="workbook",
            extension="xlsx",
            uri=f"memory://{reference}",
            size_bytes=len(self.contents),
            sha256="a" * 64,
        )

    def open_binary(self, reference: str) -> BinaryIO:
        self.open_calls.append(reference)
        self.last_stream = TrackingBinaryStream(self.contents)
        return self.last_stream


def _workbook() -> bytes:
    """Create a minimal two-worksheet XLSX document entirely in memory."""
    contents = BytesIO()
    with ZipFile(contents, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
<Default Extension=\"xml\" ContentType=\"application/xml\"/>
<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>
<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
<Override PartName=\"/xl/worksheets/sheet2.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">
<sheets><sheet name=\"Sales\" sheetId=\"1\" r:id=\"rId1\"/><sheet name=\"Summary\" sheetId=\"2\" r:id=\"rId2\"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>
<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet2.xml\"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet("region", "revenue", "West", "42"))
        archive.writestr("xl/worksheets/sheet2.xml", _worksheet("metric", "value", "records", "2"))
    return contents.getvalue()


def _worksheet(first_header: str, second_header: str, first_value: str, second_value: str) -> str:
    """Return a small worksheet XML document using inline string values."""
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>
<row r=\"1\"><c r=\"A1\" t=\"inlineStr\"><is><t>{first_header}</t></is></c><c r=\"B1\" t=\"inlineStr\"><is><t>{second_header}</t></is></c></row>
<row r=\"2\"><c r=\"A2\" t=\"inlineStr\"><is><t>{first_value}</t></is></c><c r=\"B2\"><v>{second_value}</v></c></row>
</sheetData></worksheet>"""


def test_load_returns_tabular_result_from_provider_backed_workbook() -> None:
    """The default selection should load the first worksheet from a binary stream."""
    provider = InMemoryStorageProvider("sample/workbook.xlsx", _workbook())

    result = ExcelLoader(provider).load("sample/workbook.xlsx")

    assert isinstance(result, TabularLoadResult)
    assert provider.describe_calls == ["sample/workbook.xlsx"]
    assert provider.open_calls == ["sample/workbook.xlsx"]
    assert result.asset.uri == "memory://sample/workbook.xlsx"
    assert result.dataframe.to_dicts() == [{"region": "West", "revenue": 42}]
    assert result.row_count == 1
    assert result.column_count == 2
    assert result.column_names == ["region", "revenue"]
    assert result.estimated_size_bytes == result.dataframe.estimated_size()
    assert provider.last_stream is not None
    assert provider.last_stream.was_closed


def test_load_supports_worksheet_name_selection() -> None:
    """A worksheet name should select the named worksheet."""
    provider = InMemoryStorageProvider("sample/workbook.xlsx", _workbook())

    options = ExcelLoadOptions(worksheet="Summary")

    result = ExcelLoader(provider).load("sample/workbook.xlsx", options)

    assert result.dataframe.to_dicts() == [{"metric": "records", "value": 2}]


def test_load_supports_positive_worksheet_id_selection() -> None:
    """A positive worksheet ID should select one worksheet."""
    provider = InMemoryStorageProvider("sample/workbook.xlsx", _workbook())

    result = ExcelLoader(provider).load("sample/workbook.xlsx", ExcelLoadOptions(worksheet=2))

    assert result.dataframe.to_dicts() == [{"metric": "records", "value": 2}]


def test_load_supports_excel_read_options() -> None:
    """The loader should pass supported parsing options to Polars."""
    provider = InMemoryStorageProvider("sample/workbook.xlsx", _workbook())

    result = ExcelLoader(provider).load(
        "sample/workbook.xlsx",
        ExcelLoadOptions(schema_overrides={"revenue": pl.Int64}, infer_schema_length=10),
    )

    assert result.dataframe.schema == {"region": pl.String, "revenue": pl.Int64}


def test_load_propagates_storage_errors_unchanged() -> None:
    """Provider-owned failures must not be wrapped by the Excel loader."""

    class MissingStorageProvider:
        def describe(self, reference: str) -> StorageAsset:
            raise StorageAssetNotFoundError(reference)

        def open_binary(self, reference: str) -> BinaryIO:
            return BytesIO()

    with pytest.raises(StorageAssetNotFoundError):
        ExcelLoader(MissingStorageProvider()).load("sample/missing.xlsx")


def test_load_wraps_malformed_workbook_errors() -> None:
    """Workbook parser failures should be surfaced as loader-owned exceptions."""
    provider = InMemoryStorageProvider("sample/broken.xlsx", b"not an Excel workbook")

    with pytest.raises(ExcelLoadError):
        ExcelLoader(provider).load("sample/broken.xlsx")


@pytest.mark.parametrize(
    "options",
    [
        ExcelLoadOptions(worksheet=0),
        ExcelLoadOptions(worksheet=True),
        ExcelLoadOptions(worksheet="  "),
        ExcelLoadOptions(infer_schema_length=0),
    ],
)
def test_load_rejects_invalid_options_before_storage_access(options: ExcelLoadOptions) -> None:
    """Invalid loader options should fail before storage is accessed."""
    provider = InMemoryStorageProvider("sample/workbook.xlsx", _workbook())

    with pytest.raises(ExcelLoadError):
        ExcelLoader(provider).load("sample/workbook.xlsx", options)

    assert provider.describe_calls == []
    assert provider.open_calls == []
