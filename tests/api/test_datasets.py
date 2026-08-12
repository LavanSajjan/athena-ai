"""Tests for the dataset REST API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packages.core.application import create_application
from packages.domains.dataset.service import DatasetService
from packages.services.dataset_profiling_service import DatasetProfilingService
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

    with TestClient(app) as test_client:
        yield test_client


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


def test_system_endpoints_remain_available(client: TestClient) -> None:
    """Dataset routing should not disturb existing system endpoints."""
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/version").status_code == 200
