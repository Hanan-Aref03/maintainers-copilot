from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.infra.artifact_store import BucketedArtifactStore, bucket_root_path

logger = logging.getLogger(__name__)


class EvalArtifactError(RuntimeError):
    pass


class EvalArtifactService:
    def __init__(self, artifact_store: BucketedArtifactStore | None = None) -> None:
        self.store = artifact_store or BucketedArtifactStore(
            settings.minio_eval_bucket,
            root_prefix="runs",
        )

    def ensure_bucket(self) -> None:
        self.store.ensure_bucket()

    def store_run(
        self,
        *,
        run_id: str,
        combined_report: dict[str, Any],
        classification_report: dict[str, Any] | None = None,
        rag_report: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.store.ensure_bucket()
        artifact_prefix = bucket_root_path(getattr(self.store, "root_prefix", ""), run_id)
        manifest = {
            "run_id": run_id,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "metadata": metadata or {},
            "artifacts": [f"{artifact_prefix}/eval_report.json"],
        }

        run_prefix = bucket_root_path(run_id)
        self.store.put_json(f"{run_prefix}/eval_report.json", combined_report)
        if classification_report is not None:
            self.store.put_json(f"{run_prefix}/classification_report.json", classification_report)
            manifest["artifacts"].append(f"{artifact_prefix}/classification_report.json")
        if rag_report is not None:
            self.store.put_json(f"{run_prefix}/rag_report.json", rag_report)
            manifest["artifacts"].append(f"{artifact_prefix}/rag_report.json")

        self.store.put_json(f"{run_prefix}/manifest.json", manifest)
        self.store.put_json("latest/manifest.json", manifest)
        logger.info("Mirrored eval artifacts to MinIO bucket %s", self.store.bucket_name)
        return manifest
