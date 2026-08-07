"""Tests for the local filesystem storage provider."""

import hashlib
from pathlib import Path

import pytest

from packages.shared.exceptions import (
    InvalidStorageReferenceError,
    StorageAssetNotFoundError,
)
from packages.storage.blob.local import LocalStorageProvider


def test_describe_returns_local_asset_metadata(tmp_path: Path) -> None:
    """A valid relative reference should return complete canonical metadata."""
    storage_root = tmp_path / "datasets"
    asset_path = storage_root / "sample" / "Sales.CSV"
    asset_path.parent.mkdir(parents=True)
    contents = b"region,revenue\nwest,42\n"
    asset_path.write_bytes(contents)
    provider = LocalStorageProvider(storage_root)

    asset = provider.describe("sample/Sales.CSV")

    assert asset.reference == "sample/Sales.CSV"
    assert asset.name == "Sales"
    assert asset.extension == "csv"
    assert asset.uri == asset_path.resolve().as_uri()
    assert asset.size_bytes == len(contents)
    assert asset.sha256 == hashlib.sha256(contents).hexdigest()


def test_describe_hashes_large_files(tmp_path: Path) -> None:
    """Hashing should handle content larger than the provider chunk size."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    contents = b"a" * (LocalStorageProvider._HASH_CHUNK_SIZE + 1)
    (storage_root / "large.csv").write_bytes(contents)
    provider = LocalStorageProvider(storage_root)

    asset = provider.describe("large.csv")

    assert asset.sha256 == hashlib.sha256(contents).hexdigest()


def test_open_binary_returns_asset_content(tmp_path: Path) -> None:
    """Binary streams should begin at the first byte of the selected asset."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    contents = b"dataset content"
    (storage_root / "sales.csv").write_bytes(contents)
    provider = LocalStorageProvider(storage_root)

    with provider.open_binary("sales.csv") as asset_file:
        assert asset_file.read() == contents


def test_describe_rejects_missing_assets(tmp_path: Path) -> None:
    """Missing references should raise a typed not-found exception."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    provider = LocalStorageProvider(storage_root)

    with pytest.raises(StorageAssetNotFoundError):
        provider.describe("missing.csv")


def test_describe_rejects_directory_references(tmp_path: Path) -> None:
    """Directory references must not be treated as dataset assets."""
    storage_root = tmp_path / "datasets"
    (storage_root / "sample").mkdir(parents=True)
    provider = LocalStorageProvider(storage_root)

    with pytest.raises(InvalidStorageReferenceError):
        provider.describe("sample")


def test_describe_rejects_empty_and_absolute_references(tmp_path: Path) -> None:
    """References must be non-empty paths relative to the configured root."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    provider = LocalStorageProvider(storage_root)

    with pytest.raises(InvalidStorageReferenceError):
        provider.describe("")

    with pytest.raises(InvalidStorageReferenceError):
        provider.describe(str((tmp_path / "outside.csv").resolve()))


def test_describe_rejects_references_outside_storage_root(tmp_path: Path) -> None:
    """Traversal references must not escape the configured storage root."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    outside_asset = tmp_path / "outside.csv"
    outside_asset.write_text("restricted")
    provider = LocalStorageProvider(storage_root)

    with pytest.raises(InvalidStorageReferenceError):
        provider.describe("../outside.csv")
