"""Tests for the dataset REST API."""

# ruff: noqa: E501

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from packages.core.application import create_application
from packages.domains.dataset.service import DatasetService
from packages.services.dataset_profiling_service import DatasetProfilingService
from packages.services.dataset_query_service import DatasetQueryService
from packages.storage.blob.local import LocalStorageProvider


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Create an application client with isolated, temporary dataset storage."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    app = create_application()
    storage_provider = LocalStorageProvider(storage_root)
    dataset_service = DatasetService(storage_provider)
    app.state.dataset_service = dataset_service
    app.state.dataset_profiling_service = DatasetProfilingService(
        dataset_service,
        storage_provider,
    )
    app.state.dataset_query_service = DatasetQueryService(
        dataset_service,
        storage_provider,
    )

    with TestClient(app) as test_client:
        yield test_client


def _workbook() -> bytes:
    """Create a minimal XLSX workbook with one sales worksheet."""
    contents = BytesIO()
    with ZipFile(contents, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="inlineStr"><is><t>region</t></is></c><c r="B1" t="inlineStr"><is><t>revenue</t></is></c></row>
<row r="2"><c r="A2" t="inlineStr"><is><t>West</t></is></c><c r="B2"><v>42</v></c></row>
</sheetData></worksheet>""",
        )
    return contents.getvalue()


def test_register_dataset_returns_registered_dataset(client: TestClient, tmp_path: Path) -> None:
    """POST should register an existing asset and return its dataset metadata."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    contents = b"id,revenue\n1,42\n"
    asset_path.write_bytes(contents)

    response = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "sales"
    assert body["source_type"] == "csv"
    assert body["asset_uri"] == asset_path.resolve().as_uri()
    assert body["size_bytes"] == len(contents)
    assert body["status"] == "registered"
    assert body["sha256"] is not None
    assert body["extension"] == ".csv"


def test_list_datasets_persists_registration_across_requests(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """POST and GET collection should share one application-scoped registry."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"id,revenue\n1,42\n")

    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})
    listing = client.get("/api/v1/datasets")

    assert registration.status_code == 201
    assert listing.status_code == 200
    assert listing.json() == [registration.json()]


def test_get_dataset_returns_registered_dataset(client: TestClient, tmp_path: Path) -> None:
    """GET by identifier should return the dataset previously registered through the API."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"id,revenue\n1,42\n")

    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})
    dataset_id = registration.json()["id"]
    response = client.get(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 200
    assert response.json() == registration.json()


def test_get_unknown_dataset_returns_not_found(client: TestClient) -> None:
    """GET by an unknown UUID should return an HTTP 404 response."""
    response = client.get("/api/v1/datasets/ed363fe0-82a4-4cba-851e-7b0c6f1d5c06")

    assert response.status_code == 404


def test_register_missing_dataset_returns_not_found(client: TestClient) -> None:
    """POST should map a missing storage reference to an HTTP 404 response."""
    response = client.post("/api/v1/datasets", json={"reference": "sample/missing.csv"})

    assert response.status_code == 404


def test_profile_dataset_uses_retained_reference_and_returns_profile(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Profiling should reload the registered source using its opaque reference."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(
        b"order_id,status,amount,ordered_on,empty\n"
        b"101,new,12.5,2026-01-01,\n"
        b"102,paid,9.0,2026-01-02,\n"
        b"102,paid,9.0,2026-01-02,\n"
        b"103,paid,10.0,2026-01-03,\n"
        b"104,new,5.0,2026-01-04,\n"
    )
    reference = "sample/../sample/sales.csv"

    registration = client.post("/api/v1/datasets", json={"reference": reference})
    response = client.post(f"/api/v1/datasets/{registration.json()['id']}/profile")

    assert registration.status_code == 201
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["reference"] == reference
    assert body["summary"]["name"] == "sales"
    assert body["summary"]["row_count"] == 5
    assert body["summary"]["column_count"] == 5
    assert body["summary"]["estimated_size_bytes"] > 0
    assert body["columns"][0] == {
        "name": "order_id",
        "data_type": "Int64",
        "null_count": 0,
        "null_percentage": 0.0,
        "distinct_count": 4,
        "distinct_percentage": 80.0,
    }
    assert body["data_quality"] == {
        "total_cell_count": 25,
        "null_cell_count": 5,
        "null_percentage": 20.0,
        "duplicate_row_count": 1,
        "duplicate_row_percentage": 20.0,
        "empty_column_count": 1,
    }
    assert body["recommendations"] == {
        "potential_primary_keys": [],
        "identifier_columns": [],
        "categorical_columns": ["status", "empty"],
        "numeric_measures": ["order_id", "amount"],
        "date_dimensions": [],
    }


def test_profile_unknown_dataset_returns_not_found(client: TestClient) -> None:
    """Profiling an unknown UUID should return an HTTP 404 response."""
    response = client.post("/api/v1/datasets/ed363fe0-82a4-4cba-851e-7b0c6f1d5c06/profile")

    assert response.status_code == 404


def test_profile_missing_registered_asset_returns_not_found(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Profiling should surface a source asset deleted after registration."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"id\n1\n")
    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})
    asset_path.unlink()

    response = client.post(f"/api/v1/datasets/{registration.json()['id']}/profile")

    assert registration.status_code == 201
    assert response.status_code == 404


def test_profile_unsupported_format_returns_unprocessable_entity(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Profiling an unsupported registered format should return an HTTP 422 response."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "records.json"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"[]")
    registration = client.post("/api/v1/datasets", json={"reference": "sample/records.json"})

    response = client.post(f"/api/v1/datasets/{registration.json()['id']}/profile")

    assert registration.status_code == 201
    assert response.status_code == 422


def test_query_dataset_uses_shared_registry_retained_reference_and_serializes_result(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Querying a registered CSV reloads its opaque reference through the shared service."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"region,revenue\nWest,12\nEast,8\nWest,20\n")
    reference = "sample/../sample/sales.csv"

    registration = client.post("/api/v1/datasets", json={"reference": reference})
    response = client.post(
        f"/api/v1/datasets/{registration.json()['id']}/query",
        json={
            "sql": "SELECT region, SUM(revenue) AS total FROM dataset "
            "GROUP BY region ORDER BY region"
        },
    )

    assert registration.status_code == 201
    assert response.status_code == 200
    assert response.json()["sql"] == (
        "SELECT region, SUM(revenue) AS total FROM dataset GROUP BY region ORDER BY region"
    )
    assert response.json()["rows"] == [
        {"region": "East", "total": "8"},
        {"region": "West", "total": "32"},
    ]
    assert response.json()["row_count"] == 2
    assert response.json()["column_count"] == 2
    assert response.json()["execution_time_ms"] >= 0


def test_query_excel_dataset_returns_rows(client: TestClient, tmp_path: Path) -> None:
    """Querying a registered Excel workbook uses the existing Excel loader."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.xlsx"
    asset_path.parent.mkdir()
    asset_path.write_bytes(_workbook())

    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.xlsx"})
    response = client.post(
        f"/api/v1/datasets/{registration.json()['id']}/query",
        json={"sql": "SELECT * FROM dataset"},
    )

    assert registration.status_code == 201
    assert response.status_code == 200
    assert response.json()["rows"] == [{"region": "West", "revenue": 42}]


def test_query_unknown_dataset_returns_not_found(client: TestClient) -> None:
    """Querying an unknown UUID should return an HTTP 404 response."""
    response = client.post(
        "/api/v1/datasets/ed363fe0-82a4-4cba-851e-7b0c6f1d5c06/query",
        json={"sql": "SELECT * FROM dataset"},
    )

    assert response.status_code == 404


def test_query_missing_registered_asset_returns_not_found(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Querying should surface a source asset deleted after registration."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"id\n1\n")
    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})
    asset_path.unlink()

    response = client.post(
        f"/api/v1/datasets/{registration.json()['id']}/query",
        json={"sql": "SELECT * FROM dataset"},
    )

    assert registration.status_code == 201
    assert response.status_code == 404


@pytest.mark.parametrize("sql", ["  \n", "DELETE FROM dataset", "SELECT * FROM dataset;"])
def test_query_rejects_non_read_only_sql(client: TestClient, sql: str) -> None:
    """The public query endpoint should enforce its narrow SELECT-only policy."""
    response = client.post(
        "/api/v1/datasets/ed363fe0-82a4-4cba-851e-7b0c6f1d5c06/query",
        json={"sql": sql},
    )

    assert response.status_code == 422


def test_query_invalid_select_returns_unprocessable_entity(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """DuckDB query failures should be exposed as HTTP 422 responses."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "sales.csv"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"id\n1\n")
    registration = client.post("/api/v1/datasets", json={"reference": "sample/sales.csv"})

    response = client.post(
        f"/api/v1/datasets/{registration.json()['id']}/query",
        json={"sql": "SELECT missing FROM dataset"},
    )

    assert registration.status_code == 201
    assert response.status_code == 422


def test_query_unsupported_format_returns_unprocessable_entity(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """Querying a registered unsupported format should return HTTP 422."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "records.json"
    asset_path.parent.mkdir()
    asset_path.write_bytes(b"[]")
    registration = client.post("/api/v1/datasets", json={"reference": "sample/records.json"})

    response = client.post(
        f"/api/v1/datasets/{registration.json()['id']}/query",
        json={"sql": "SELECT * FROM dataset"},
    )

    assert registration.status_code == 201
    assert response.status_code == 422


def test_system_endpoints_remain_available(client: TestClient) -> None:
    """Dataset routing should not disturb existing system endpoints."""
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/version").status_code == 200
