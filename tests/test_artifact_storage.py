from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from app.infra.artifact_store import BucketedArtifactStore
from app.infra.blob_store import BlobObject
from app.services.chat_service import ChatService
from app.services.conversation_snapshot_service import ConversationSnapshotService
from app.services.eval_artifact_service import EvalArtifactService
from app.services.model_artifact_service import ModelArtifactService


class FakeArtifactStore:
    def __init__(self, bucket_name: str = "test-bucket", root_prefix: str = "") -> None:
        self.bucket_name = bucket_name
        self.root_prefix = root_prefix
        self.calls: list[tuple[str, str, object]] = []
        self.prune_calls: list[tuple[str, int]] = []

    def ensure_bucket(self) -> None:
        self.calls.append(("ensure_bucket", "", None))

    def put_json(self, relative_key: str, payload):
        self.calls.append(("put_json", relative_key, payload))
        return relative_key

    def put_bytes(self, relative_key: str, data: bytes, *, content_type: str | None = None):
        self.calls.append(("put_bytes", relative_key, {"size": len(data), "content_type": content_type}))
        return relative_key

    def put_text(self, relative_key: str, text: str, *, content_type: str = "text/plain; charset=utf-8"):
        self.calls.append(("put_text", relative_key, {"text": text, "content_type": content_type}))
        return relative_key

    def prune_prefix(self, relative_prefix: str, *, keep_last: int):
        self.prune_calls.append((relative_prefix, keep_last))
        return []


class FakeMinioClient:
    def __init__(self, objects: list[BlobObject]) -> None:
        self.objects = objects
        self.deleted: list[str] = []

    def ensure_bucket(self) -> None:
        return None

    def put_object(self, *args, **kwargs) -> None:
        return None

    def list_objects(self, prefix: str = "", max_keys: int = 1000):
        return self.objects

    def delete_object(self, key: str) -> None:
        self.deleted.append(key)


def test_bucketed_artifact_store_prunes_old_objects():
    store = BucketedArtifactStore("bucket", root_prefix="threads")
    store.client = FakeMinioClient(
        [
            BlobObject(
                key="threads/thread-a/20260101T000000Z-old.json",
                size_bytes=10,
                last_modified="2026-01-01T00:00:00Z",
            ),
            BlobObject(
                key="threads/thread-a/20260102T000000Z-new.json",
                size_bytes=12,
                last_modified="2026-01-02T00:00:00Z",
            ),
            BlobObject(
                key="threads/thread-a/20260103T000000Z-newest.json",
                size_bytes=12,
                last_modified="2026-01-03T00:00:00Z",
            ),
        ]
    )

    deleted = store.prune_prefix("thread-a", keep_last=2)

    assert deleted == ["threads/thread-a/20260101T000000Z-old.json"]
    assert store.client.deleted == ["threads/thread-a/20260101T000000Z-old.json"]


def test_model_artifact_service_stores_versioned_run(tmp_path):
    model_path = tmp_path / "fine_tuned_classifier.joblib"
    model_path.write_bytes(b"binary-model")
    fake_store = FakeArtifactStore("copilot-model-artifacts", root_prefix="classification")
    service = ModelArtifactService(artifact_store=fake_store)

    manifest = service.store_classifier_run(
        training_hash="train-hash-123",
        model_card={
            "training_data_hash": "train-hash-123",
            "splits": {"train": 8, "val": 4, "test": 4},
            "validation_metrics": {"macro_f1": 0.91},
        },
        model_path=model_path,
    )

    assert manifest["artifact_prefix"] == "classification/fine_tuned_classifier/train-hash-123"
    assert "classification/fine_tuned_classifier/train-hash-123/model_card.json" in manifest["artifacts"]
    assert any(call[0] == "put_text" and call[1].endswith("training_summary.svg") for call in fake_store.calls)
    assert any(call[0] == "put_bytes" and call[1].endswith("fine_tuned_classifier.joblib") for call in fake_store.calls)
    assert any(call[0] == "put_json" and call[1] == "latest/manifest.json" for call in fake_store.calls)


def test_eval_artifact_service_stores_separate_reports():
    fake_store = FakeArtifactStore("copilot-eval-artifacts", root_prefix="runs")
    service = EvalArtifactService(artifact_store=fake_store)

    manifest = service.store_run(
        run_id="run-20260522",
        combined_report={"classification": {"macro_f1": 0.8}, "rag": {"hit_at_5": 1.0}},
        classification_report={"models": {"fine": {"macro_f1": 0.8}}},
        rag_report={"hit_at_5": 1.0},
        metadata={"source": "ci"},
    )

    assert manifest["run_id"] == "run-20260522"
    assert "runs/run-20260522/eval_report.json" in manifest["artifacts"]
    assert "runs/run-20260522/classification_report.json" in manifest["artifacts"]
    assert "runs/run-20260522/rag_report.json" in manifest["artifacts"]
    assert any(call[1] == "latest/manifest.json" for call in fake_store.calls if call[0] == "put_json")


def test_chat_service_records_snapshot(monkeypatch):
    fake_snapshot_store = FakeArtifactStore("copilot-conversation-snapshots")
    snapshot_service = ConversationSnapshotService(artifact_store=fake_snapshot_store)
    chat_service = ChatService(db=None, snapshot_service=snapshot_service)

    async def fake_load_short_term_messages(thread_id):
        return []

    async def fake_load_rag_context(message):
        return [{"id": "doc-1", "title": "Crash on startup", "body": "The app crashes on startup."}]

    async def fake_append_short_term_message(thread_id, role, content):
        return None

    monkeypatch.setattr(chat_service, "_load_short_term_messages", fake_load_short_term_messages)
    monkeypatch.setattr(chat_service, "_load_rag_context", fake_load_rag_context)
    monkeypatch.setattr(chat_service, "_append_short_term_message", fake_append_short_term_message)

    async def fake_embed(_message):
        return None

    monkeypatch.setattr(chat_service, "_maybe_embed", fake_embed)
    monkeypatch.setattr(chat_service, "_load_memories", lambda user_id: [])
    monkeypatch.setattr(chat_service, "_build_fallback_reply", lambda message, memory_context, rag_context: "fallback reply")
    chat_service.gemini = None

    result = asyncio.run(
        chat_service.process_message_with_metadata(
            user_id=UUID("00000000-0000-0000-0000-000000000111"),
            thread_id="thread/alpha",
            message="What happened?",
        )
    )

    assert result["used_fallback"] is True
    assert fake_snapshot_store.calls
    put_call = next(call for call in fake_snapshot_store.calls if call[0] == "put_json")
    assert put_call[1].startswith("thread_alpha/")
    assert put_call[2]["retrieved_doc_ids"] == ["doc-1"]
    assert fake_snapshot_store.prune_calls == [("thread_alpha", 25)]
