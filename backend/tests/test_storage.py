"""Storage backends and migration copy (no database needed)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.storage import LocalStorage, S3Storage, StorageError, copy_all


def test_local_storage_roundtrip_and_listing(tmp_path: Path) -> None:
    store = LocalStorage(str(tmp_path))
    store.put("properties/a/1.webp", b"one", "image/webp")
    store.put("documents/b/2.pdf", b"two", "application/pdf")
    assert store.get("properties/a/1.webp") == b"one"
    assert list(store.iter_keys()) == ["documents/b/2.pdf", "properties/a/1.webp"]
    assert list(store.iter_keys("properties/")) == ["properties/a/1.webp"]
    with pytest.raises(StorageError):
        store.put("../escape", b"x", "text/plain")
    with pytest.raises(StorageError):
        store.get("properties/missing.webp")


def test_copy_all_is_idempotent(tmp_path: Path) -> None:
    source = LocalStorage(str(tmp_path / "cloud"))
    target = LocalStorage(str(tmp_path / "pc"))
    for i in range(3):
        source.put(f"properties/p/{i}.webp", bytes([i]), "image/webp")
    assert copy_all(source, target) == {"copied": 3, "skipped": 0}
    assert copy_all(source, target) == {"copied": 0, "skipped": 3}
    assert target.get("properties/p/2.webp") == b"\x02"


@pytest.fixture
def s3_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    import boto3
    import moto

    with moto.mock_aws():
        settings = get_settings()
        for key, value in {
            "s3_bucket": "media",
            "s3_endpoint_url": None,
            "s3_region": "us-east-1",
            "s3_access_key_id": "test",
            "s3_secret_access_key": "test",
        }.items():
            monkeypatch.setattr(settings, key, value)
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="media")
        yield


def test_s3_storage_against_in_process_s3(s3_settings: None, tmp_path: Path) -> None:
    store = S3Storage()
    store.put("properties/x/1.webp", b"img", "image/webp")
    assert store.exists("properties/x/1.webp")
    assert store.get("properties/x/1.webp") == b"img"
    assert list(store.iter_keys("properties/")) == ["properties/x/1.webp"]
    store.delete("properties/x/1.webp")
    assert not store.exists("properties/x/1.webp")
    with pytest.raises(StorageError):
        store.get("properties/x/1.webp")

    # Cloud bucket → local disk on the production PC.
    store.put("documents/d/deed.pdf", b"%PDF-1.7", "application/pdf")
    local = LocalStorage(str(tmp_path))
    assert copy_all(store, local) == {"copied": 1, "skipped": 0}
    assert local.get("documents/d/deed.pdf") == b"%PDF-1.7"
