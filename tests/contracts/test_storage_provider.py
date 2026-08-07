"""Behavioral contract tests for storage provider implementations."""

import re
from pathlib import Path

from packages.storage.blob.local import LocalStorageProvider


def test_local_storage_provider_satisfies_asset_contract(tmp_path: Path) -> None:
    """The local adapter should expose complete provider-neutral asset metadata."""
    storage_root = tmp_path / "datasets"
    storage_root.mkdir()
    contents = b"id,value\n1,one\n"
    (storage_root / "records.csv").write_bytes(contents)
    provider = LocalStorageProvider(storage_root)

    asset = provider.describe("records.csv")

    assert asset.name == "records"
    assert asset.extension == "csv"
    assert asset.size_bytes == len(contents)
    assert re.fullmatch(r"[0-9a-f]{64}", asset.sha256) is not None

    with provider.open_binary(asset.reference) as asset_file:
        assert asset_file.read() == contents
