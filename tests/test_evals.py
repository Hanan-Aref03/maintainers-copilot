from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import evals.classification_eval as classification_eval
import evals.rag_eval as rag_eval


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_classification_eval_aggregates_metrics(monkeypatch, tmp_path):
    golden = [
        {"id": 1, "title": "Bug: crash", "body": "This crashes", "true_label": "bug"},
        {"id": 2, "title": "Docs: typo", "body": "Fix docs", "true_label": "docs"},
    ]
    golden_path = tmp_path / "classification_golden.json"
    golden_path.write_text(json.dumps(golden), encoding="utf-8")

    def fake_post(url, json, timeout):
        title = json["title"]
        model = json["model"]
        label = "bug" if "Bug" in title else "docs"
        used_fallback = model == "few"
        return FakeResponse(
            {
                "label": label,
                "used_fallback": used_fallback,
                "classifier_source": "rule_fallback" if used_fallback else model,
                "fallback_reason": "provider_error" if used_fallback else None,
            }
        )

    monkeypatch.setattr(classification_eval.requests, "post", fake_post)

    report = classification_eval.evaluate_classification_models(golden_path, models=("rule", "few"))

    assert report["num_models"] == 2
    assert report["models"]["rule"]["macro_f1"] == 1.0
    assert report["models"]["few"]["macro_f1"] == 1.0
    assert report["models"]["few"]["fallback_count"] == 2
    assert report["models"]["few"]["fallback_rate"] == 1.0


def test_rag_eval_computes_required_metrics(monkeypatch, tmp_path):
    golden = [
        {
            "question": "What bug is described?",
            "answer": "The issue describes a crash on startup.",
            "ground_truth_doc_id": 42,
            "context": "Bug: crash on startup\nThe app crashes on startup.",
        }
    ]
    golden_path = tmp_path / "rag_golden.json"
    golden_path.write_text(json.dumps(golden), encoding="utf-8")

    class FakeChatService:
        def __init__(self, db=None):
            self.db = db

        async def process_message_with_metadata(self, user_id, thread_id, message):
            return {
                "response": "The issue describes a crash on startup.",
                "used_fallback": True,
                "llm_provider": "local",
                "retrieved_doc_ids": [42],
                "retrieved_contexts": ["Bug: crash on startup\nThe app crashes on startup."],
                "fallback_reason": "provider_error",
            }

    class FakeFaithfulnessMetric:
        async def ascore(self, user_input, response, retrieved_contexts):
            return SimpleNamespace(value=0.9)

    class FakeAnswerRelevancyMetric:
        async def ascore(self, user_input, response):
            return SimpleNamespace(value=0.8)

    monkeypatch.setattr(rag_eval, "ChatService", FakeChatService)
    monkeypatch.setattr(
        rag_eval,
        "build_ragas_metrics",
        lambda llm, embeddings: [FakeFaithfulnessMetric(), FakeAnswerRelevancyMetric()],
    )

    report = asyncio.run(rag_eval.evaluate_rag(golden_path))

    assert report["hit_at_5"] == 1.0
    assert report["mrr_at_10"] == 1.0
    assert report["faithfulness"] == 0.9
    assert report["answer_relevancy"] == 0.8
    assert report["fallback_count"] == 1
    assert report["ragas_status"] == "ok"
