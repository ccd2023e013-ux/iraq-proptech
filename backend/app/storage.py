"""Object storage behind a small interface.

* ``LocalStorage`` (default): files under ``STORAGE_LOCAL_PATH`` — development,
  Codespaces and the production PC (mount a volume or point at a disk).
* ``S3Storage``: any S3-compatible service — MinIO on the production PC,
  Supabase Storage (S3 protocol), Cloudflare R2, AWS S3 — chosen by config only.

Keys are opaque server-generated paths; user-supplied names never become
paths, so there is no path traversal.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings

_SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9/_.-]{0,299}$")


class StorageError(Exception):
    pass


def _check_key(key: str) -> str:
    if not _SAFE_KEY.match(key) or ".." in key or "//" in key:
        raise StorageError("Invalid storage key")
    return key


class Storage(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def iter_keys(self, prefix: str = "") -> Iterator[str]: ...


class LocalStorage:
    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / _check_key(key)).resolve()
        if self.root not in path.parents:
            raise StorageError("Invalid storage key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # atomic on the same filesystem

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("Object not found") from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def iter_keys(self, prefix: str = "") -> Iterator[str]:
        if not self.root.is_dir():
            return
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and not path.name.endswith(".tmp"):
                key = path.relative_to(self.root).as_posix()
                if key.startswith(prefix):
                    yield key


class S3Storage:
    name = "s3"

    def __init__(self) -> None:
        import boto3  # optional dependency, only needed when STORAGE_BACKEND=s3

        settings = get_settings()
        self.bucket = settings.s3_bucket or ""
        if not self.bucket:
            raise StorageError("S3_BUCKET is not configured")
        from botocore.config import Config

        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            # Path-style URLs work with MinIO, Supabase Storage and R2 as well as AWS.
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=_check_key(key), Body=data, ContentType=content_type
        )

    def get(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=_check_key(key))
        except Exception as exc:  # botocore raises a family of ClientErrors
            raise StorageError("Object not found") from exc
        return bytes(obj["Body"].read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=_check_key(key))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=_check_key(key))
            return True
        except Exception:
            return False

    def iter_keys(self, prefix: str = "") -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                yield str(item["Key"])


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage(settings.storage_local_path)


def copy_all(source: Storage, target: Storage, prefix: str = "") -> dict[str, int]:
    """Copy every object (idempotent: existing keys are skipped). Used for migrations."""
    copied = skipped = 0
    for key in source.iter_keys(prefix):
        if target.exists(key):
            skipped += 1
            continue
        target.put(key, source.get(key), _content_type(key))
        copied += 1
    return {"copied": copied, "skipped": skipped}


def _content_type(key: str) -> str:
    import mimetypes

    return mimetypes.guess_type(key)[0] or "application/octet-stream"
