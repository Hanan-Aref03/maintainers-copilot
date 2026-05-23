from __future__ import annotations

import logging

from app.core.config import settings
from app.infra.artifact_store import ensure_bucket_names

logger = logging.getLogger(__name__)


def ensure_minio_storage() -> dict[str, bool]:
    buckets = {
        "attachments": settings.minio_bucket,
        "model_artifacts": settings.minio_model_bucket,
        "eval_artifacts": settings.minio_eval_bucket,
        "conversation_snapshots": settings.minio_snapshot_bucket,
    }
    status = ensure_bucket_names(list(buckets.values()))
    named_status = {name: status.get(bucket_name, False) for name, bucket_name in buckets.items()}

    failed = [name for name, ok in named_status.items() if not ok]
    if failed:
        logger.warning("MinIO buckets not ready: %s", ", ".join(failed))
    else:
        logger.info("All MinIO buckets are ready")

    return named_status
