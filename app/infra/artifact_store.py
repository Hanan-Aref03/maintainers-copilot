from __future__ import annotations

import logging
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.infra.blob_store import BlobObject, get_blob_store

logger = logging.getLogger(__name__)

_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._/-]+")


def sanitize_artifact_component(value: str | None) -> str:
    candidate = (value or "").strip().replace("\\", "/")
    candidate = candidate.strip("/")
    candidate = _SAFE_COMPONENT_RE.sub("_", candidate)
    return candidate or "default"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None


class BucketedArtifactStore:
    def __init__(self, bucket_name: str, *, root_prefix: str = "") -> None:
        self.bucket_name = bucket_name.strip()
        self.root_prefix = sanitize_artifact_component(root_prefix)
        self.client = get_blob_store(self.bucket_name)

    def ensure_bucket(self) -> None:
        self.client.ensure_bucket()

    def _relative_key(self, relative_key: str) -> str:
        key = relative_key.strip().lstrip("/")
        if self.root_prefix:
            return f"{self.root_prefix}/{key}" if key else self.root_prefix
        return key

    def _full_prefix(self, relative_prefix: str = "") -> str:
        relative_prefix = relative_prefix.strip().lstrip("/")
        if self.root_prefix and relative_prefix:
            return f"{self.root_prefix}/{relative_prefix}"
        if self.root_prefix:
            return self.root_prefix
        return relative_prefix

    def put_bytes(self, relative_key: str, data: bytes, *, content_type: str | None = None) -> str:
        key = self._relative_key(relative_key)
        self.client.put_object(key, data, content_type=content_type)
        return key

    def put_text(
        self,
        relative_key: str,
        text: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
    ) -> str:
        return self.put_bytes(relative_key, text.encode("utf-8"), content_type=content_type)

    def put_json(self, relative_key: str, payload: Any) -> str:
        return self.put_text(
            relative_key,
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            content_type="application/json; charset=utf-8",
        )

    def get_bytes(self, relative_key: str) -> bytes:
        return self.client.get_object(self._relative_key(relative_key))

    def get_json(self, relative_key: str) -> Any:
        return json.loads(self.get_bytes(relative_key).decode("utf-8"))

    def list_objects(self, relative_prefix: str = "") -> list[BlobObject]:
        return self.client.list_objects(prefix=self._full_prefix(relative_prefix))

    def delete(self, relative_key: str) -> None:
        self.client.delete_object(self._relative_key(relative_key))

    def prune_prefix(self, relative_prefix: str, *, keep_last: int) -> list[str]:
        if keep_last < 0:
            keep_last = 0

        objects = self.list_objects(relative_prefix)
        objects = sorted(
            objects,
            key=lambda item: (
                _parse_timestamp(item.last_modified) or datetime.min.replace(tzinfo=timezone.utc),
                item.key,
            ),
        )
        to_delete = objects[:-keep_last] if keep_last else objects
        deleted: list[str] = []
        for blob in to_delete:
            self.client.delete_object(blob.key)
            deleted.append(blob.key)
        return deleted


def bucket_root_path(*parts: str) -> str:
    cleaned = [sanitize_artifact_component(part) for part in parts if str(part).strip()]
    return "/".join(cleaned)


def ensure_bucket_names(bucket_names: list[str]) -> dict[str, bool]:
    status: dict[str, bool] = {}
    for bucket_name in bucket_names:
        store = get_blob_store(bucket_name)
        try:
            store.ensure_bucket()
            status[bucket_name] = True
        except Exception:
            logger.warning("Failed to ensure MinIO bucket %s", bucket_name, exc_info=True)
            status[bucket_name] = False
    return status
