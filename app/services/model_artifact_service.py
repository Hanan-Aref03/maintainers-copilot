from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.core.config import settings
from app.infra.artifact_store import BucketedArtifactStore, bucket_root_path

logger = logging.getLogger(__name__)


class ModelArtifactError(RuntimeError):
    pass


def _render_training_summary_svg(model_card: dict[str, Any]) -> str:
    splits = model_card.get("splits") or {}
    validation = model_card.get("validation_metrics") or {}

    train_count = int(splits.get("train") or 0)
    val_count = int(splits.get("val") or 0)
    test_count = int(splits.get("test") or 0)
    max_count = max(train_count, val_count, test_count, 1)

    bars = []
    colors = ["#0f766e", "#3b82f6", "#f59e0b"]
    labels = [("train", train_count), ("val", val_count), ("test", test_count)]
    for index, (label, value) in enumerate(labels):
        height = int(round((value / max_count) * 180))
        x = 110 + index * 145
        y = 290 - height
        bars.append(
            f"""
            <rect x="{x}" y="{y}" width="78" height="{height}" rx="10" fill="{colors[index]}" />
            <text x="{x + 39}" y="320" text-anchor="middle" font-size="16" fill="#0f172a">{escape(label)}</text>
            <text x="{x + 39}" y="{y - 10}" text-anchor="middle" font-size="16" font-weight="700" fill="#0f172a">{value}</text>
            """
        )

    metrics_text = ", ".join(
        f"{escape(str(key))}: {round(float(value), 3)}" for key, value in validation.items() if isinstance(value, (int, float))
    ) or "no validation metrics"

    return f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="720" height="380" viewBox="0 0 720 380" role="img" aria-label="Training summary">
      <defs>
        <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#f8fafc" />
          <stop offset="100%" stop-color="#eef2ff" />
        </linearGradient>
      </defs>
      <rect width="720" height="380" rx="24" fill="url(#bg)" />
      <text x="40" y="52" font-size="24" font-weight="700" fill="#0f172a">Fine-tuned classifier training summary</text>
      <text x="40" y="82" font-size="14" fill="#475569">Training hash: {escape(str(model_card.get("training_data_hash") or "unknown"))}</text>
      <text x="40" y="110" font-size="14" fill="#475569">Validation metrics: {escape(metrics_text)}</text>
      <line x1="70" y1="290" x2="650" y2="290" stroke="#cbd5e1" stroke-width="2" />
      {''.join(bars)}
      <text x="40" y="352" font-size="13" fill="#64748b">Generated locally and mirrored to MinIO for artifact retention.</text>
    </svg>
    """.strip()


class ModelArtifactService:
    def __init__(self, artifact_store: BucketedArtifactStore | None = None) -> None:
        self.store = artifact_store or BucketedArtifactStore(
            settings.minio_model_bucket,
            root_prefix="classification",
        )

    def ensure_bucket(self) -> None:
        self.store.ensure_bucket()

    def store_classifier_run(
        self,
        *,
        training_hash: str,
        model_card: dict[str, Any],
        model_path: Path,
    ) -> dict[str, Any]:
        self.store.ensure_bucket()
        artifact_prefix = bucket_root_path(
            getattr(self.store, "root_prefix", ""),
            "fine_tuned_classifier",
            training_hash,
        )
        model_bytes = model_path.read_bytes()
        training_summary_svg = _render_training_summary_svg(model_card)

        artifact_manifest = {
            "training_hash": training_hash,
            "artifact_prefix": artifact_prefix,
            "artifacts": [
                f"{artifact_prefix}/model_card.json",
                f"{artifact_prefix}/fine_tuned_classifier.joblib",
                f"{artifact_prefix}/training_summary.svg",
            ],
        }

        run_prefix = bucket_root_path("fine_tuned_classifier", training_hash)
        self.store.put_json(f"{run_prefix}/model_card.json", model_card)
        self.store.put_bytes(
            f"{run_prefix}/fine_tuned_classifier.joblib",
            model_bytes,
            content_type="application/octet-stream",
        )
        self.store.put_text(
            f"{run_prefix}/training_summary.svg",
            training_summary_svg,
            content_type="image/svg+xml",
        )
        self.store.put_json(f"{run_prefix}/manifest.json", artifact_manifest)
        self.store.put_json("latest/manifest.json", artifact_manifest)

        logger.info("Mirrored classifier artifacts to MinIO bucket %s", self.store.bucket_name)
        return artifact_manifest
