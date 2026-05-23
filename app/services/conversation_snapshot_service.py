from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.infra.artifact_store import BucketedArtifactStore, sanitize_artifact_component

logger = logging.getLogger(__name__)


class ConversationSnapshotError(RuntimeError):
    pass


class ConversationSnapshotService:
    def __init__(self, artifact_store: BucketedArtifactStore | None = None) -> None:
        self.store = artifact_store or BucketedArtifactStore(
            settings.minio_snapshot_bucket,
            root_prefix="threads",
        )

    def ensure_bucket(self) -> None:
        self.store.ensure_bucket()

    def record_snapshot(
        self,
        *,
        thread_id: str,
        payload: dict[str, Any],
        keep_last: int | None = None,
    ) -> str:
        self.store.ensure_bucket()
        thread_slug = sanitize_artifact_component(thread_id).replace("/", "_")
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        object_key = f"{thread_slug}/{timestamp}-{uuid4().hex[:8]}.json"

        snapshot = dict(payload)
        snapshot.setdefault("thread_id", thread_id)
        snapshot.setdefault("recorded_at", datetime.now(tz=timezone.utc).isoformat())

        self.store.put_json(object_key, snapshot)
        retention = settings.max_conversation_snapshots if keep_last is None else keep_last
        if retention >= 0:
            self.store.prune_prefix(thread_slug, keep_last=retention)

        logger.info(
            "Stored conversation snapshot for thread %s in MinIO bucket %s",
            thread_id,
            self.store.bucket_name,
        )
        return object_key
