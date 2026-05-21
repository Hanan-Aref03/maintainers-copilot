from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import google.generativeai as genai

try:  # pragma: no cover - optional at import time in minimal environments
    import joblib
except Exception:  # pragma: no cover - graceful fallback
    joblib = None


def _safe_json_loads(text: str) -> Any | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()

    for candidate in (cleaned, cleaned[cleaned.find("[") : cleaned.rfind("]") + 1], cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]):
        if not candidate or candidate == "[]":
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _append_entity(entities: list[dict[str, Any]], seen: set[tuple[Any, ...]], entity: dict[str, Any]) -> None:
    key = (
        entity.get("start"),
        entity.get("end"),
        entity.get("label"),
        entity.get("text"),
    )
    if key in seen:
        return
    seen.add(key)
    entities.append(entity)


def _issue_text(issue: dict[str, Any]) -> str:
    return f"{issue.get('title', '')}\n{issue.get('body', '')}".strip()


def _parse_created_at(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _stratified_time_split(
    items: list[dict[str, Any]],
    *,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get("true_label") or "other")].append(item)

    train: list[dict[str, Any]] = []
    val: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []

    for rows in grouped.values():
        rows = sorted(rows, key=lambda item: _parse_created_at(item.get("created_at")))
        total = len(rows)
        if total == 1:
            train.extend(rows)
            continue

        train_count = max(1, int(round(total * train_ratio)))
        val_count = max(1 if total >= 3 else 0, int(round(total * val_ratio)))
        if train_count + val_count >= total:
            overflow = train_count + val_count - (total - 1)
            if overflow > 0:
                reduction = min(overflow, max(train_count - 1, 0))
                train_count -= reduction
                overflow -= reduction
            if overflow > 0:
                reduction = min(overflow, max(val_count - 1, 0))
                val_count -= reduction
        test_count = total - train_count - val_count
        if test_count <= 0:
            if val_count > 1:
                val_count -= 1
            elif train_count > 1:
                train_count -= 1
            test_count = total - train_count - val_count

        train_end = train_count
        val_end = train_count + val_count
        train.extend(rows[:train_end])
        val.extend(rows[train_end:val_end])
        test.extend(rows[val_end:])

    return train, val, test


class FineTunedClassifier:
    def __init__(self, model_dir: str | Path):
        if joblib is None:
            raise RuntimeError("joblib is required for the fine-tuned classifier")

        self.model_dir = Path(model_dir)
        self.model_path = self.model_dir / "fine_tuned_classifier.joblib"
        self.model_card_path = self.model_dir / "model_card.json"
        self._pipeline = self._load_or_train()

    def _dataset_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data_pipeline" / "pandas_issues.json"

    def _load_dataset(self) -> list[dict[str, Any]]:
        with self._dataset_path().open(encoding="utf-8") as f:
            raw_items = json.load(f)

        records: list[dict[str, Any]] = []
        for item in raw_items:
            labels = item.get("labels") or []
            label = "other"
            lowered = [str(label_item).lower() for label_item in labels]
            if any(name in lowered for name in ["bug", "regression"]):
                label = "bug"
            elif any(name in lowered for name in ["enhancement", "feature", "new feature"]):
                label = "feature"
            elif any(name in lowered for name in ["docs", "documentation"]):
                label = "docs"
            elif any(name in lowered for name in ["question", "how-to"]):
                label = "question"

            records.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title", ""),
                    "body": item.get("body", ""),
                    "true_label": label,
                    "created_at": item.get("created_at"),
                }
            )
        return records

    def _build_pipeline(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline

        return Pipeline(
            steps=[
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        lowercase=True,
                        strip_accents="unicode",
                        max_features=6000,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=1500,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

    def _load_or_train(self):
        if self.model_path.exists():
            try:
                return joblib.load(self.model_path)
            except Exception:
                pass

        return self._train_and_save()

    def _train_and_save(self):
        from sklearn.metrics import accuracy_score, f1_score

        records = self._load_dataset()
        train_records, val_records, test_records = _stratified_time_split(records)
        train_texts = [_issue_text(item) for item in train_records]
        train_labels = [item["true_label"] for item in train_records]
        val_texts = [_issue_text(item) for item in val_records]
        val_labels = [item["true_label"] for item in val_records]

        pipeline = self._build_pipeline()
        pipeline.fit(train_texts, train_labels)

        val_metrics: dict[str, float] = {}
        if val_texts:
            val_pred = pipeline.predict(val_texts)
            val_metrics = {
                "accuracy": float(accuracy_score(val_labels, val_pred)),
                "macro_f1": float(f1_score(val_labels, val_pred, average="macro")),
            }

        final_pipeline = self._build_pipeline()
        final_texts = train_texts + val_texts
        final_labels = train_labels + val_labels
        final_pipeline.fit(final_texts, final_labels)

        self.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(final_pipeline, self.model_path)

        training_hash = hashlib.sha256(
            json.dumps(
                [{"id": item["id"], "label": item["true_label"]} for item in final_records(train_records, val_records)],
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        model_card = {
            "architecture": "tfidf + logistic_regression",
            "hyperparameters": {
                "ngram_range": [1, 2],
                "max_features": 6000,
                "class_weight": "balanced",
                "max_iter": 1500,
            },
            "training_data_hash": training_hash,
            "splits": {
                "train": len(train_records),
                "val": len(val_records),
                "test": len(test_records),
            },
            "labels": sorted({item["true_label"] for item in records}),
            "validation_metrics": val_metrics,
        }
        self.model_card_path.write_text(json.dumps(model_card, indent=2), encoding="utf-8")
        return final_pipeline

    def predict(self, title: str, body: str) -> str:
        return str(self._pipeline.predict([_issue_text({"title": title, "body": body})])[0])

    def predict_with_metadata(self, title: str, body: str) -> tuple[str, dict[str, Any]]:
        label = self.predict(title, body)
        return label, {
            "classifier_source": "fine_tuned",
            "used_fallback": False,
            "fallback_reason": None,
        }

    @property
    def ready(self) -> bool:
        return self._pipeline is not None


def final_records(*splits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for split in splits:
        combined.extend(split)
    return combined


class RuleClassifier:
    def predict(self, title, body):
        text = (title + " " + body).lower()
        if any(w in text for w in ["bug", "crash", "error", "wrong", "fix"]):
            return "bug"
        if any(w in text for w in ["feature", "add", "new", "enhance", "improve"]):
            return "feature"
        if any(w in text for w in ["doc", "tutorial", "readme", "example"]):
            return "docs"
        if any(w in text for w in ["question", "how", "why", "?"]):
            return "question"
        return "other"

    def predict_with_metadata(self, title, body) -> tuple[str, dict[str, Any]]:
        label = self.predict(title, body)
        return label, {
            "classifier_source": "rule",
            "used_fallback": False,
            "fallback_reason": None,
        }


class GeminiZeroShotClassifier:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.rule_fallback = RuleClassifier()

    def predict(self, title, body):
        label, _metadata = self.predict_with_metadata(title, body)
        return label

    def predict_with_metadata(self, title, body) -> tuple[str, dict[str, Any]]:
        prompt = f"""Classify the following GitHub issue into exactly one of: bug, feature, docs, question, other.
Title: {title}
Body: {body[:500]}
Answer only with the category name."""
        try:
            response = self.model.generate_content(prompt)
        except Exception:
            label = self.rule_fallback.predict(title, body)
            return label, {
                "classifier_source": "rule_fallback",
                "used_fallback": True,
                "fallback_reason": "provider_error",
            }

        label = response.text.strip().lower()
        if label not in ["bug", "feature", "docs", "question", "other"]:
            label = self.rule_fallback.predict(title, body)
            return label, {
                "classifier_source": "rule_fallback",
                "used_fallback": True,
                "fallback_reason": "invalid_label",
            }
        return label, {
            "classifier_source": "gemini_zero_shot",
            "used_fallback": False,
            "fallback_reason": None,
        }


class GeminiFewShotClassifier:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.rule_fallback = RuleClassifier()
        self.examples = [
            ("RuntimeError: index out of bounds", "bug"),
            ("Add support for parquet file format", "feature"),
            ("Improve API reference documentation", "docs"),
            ("How to filter DataFrame with multiple conditions?", "question"),
        ]

    def predict(self, title, body):
        label, _metadata = self.predict_with_metadata(title, body)
        return label

    def predict_with_metadata(self, title, body) -> tuple[str, dict[str, Any]]:
        example_str = "\n".join([f"Example: {ex[0]} -> {ex[1]}" for ex in self.examples])
        prompt = f"""{example_str}
Classify this issue:
Title: {title}
Body: {body[:500]}
Category (bug/feature/docs/question/other):"""
        try:
            response = self.model.generate_content(prompt)
        except Exception:
            label = self.rule_fallback.predict(title, body)
            return label, {
                "classifier_source": "rule_fallback",
                "used_fallback": True,
                "fallback_reason": "provider_error",
            }

        label = response.text.strip().lower()
        if label not in ["bug", "feature", "docs", "question", "other"]:
            label = self.rule_fallback.predict(title, body)
            return label, {
                "classifier_source": "rule_fallback",
                "used_fallback": True,
                "fallback_reason": "invalid_label",
            }
        return label, {
            "classifier_source": "gemini_few_shot",
            "used_fallback": False,
            "fallback_reason": None,
        }


class RuleEntityExtractor:
    _PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
        ("URL", re.compile(r"https?://[^\s)>\"]+")),
        ("MENTION", re.compile(r"@\w[\w-]*")),
        ("ISSUE", re.compile(r"(?<!\w)#\d+\b")),
        ("VERSION", re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?\b")),
        ("PATH", re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\b")),
        ("CODE", re.compile(r"`([^`]+)`")),
    ]

    def predict(self, text: str) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        occupied_spans: list[tuple[int, int]] = []

        for label, pattern in self._PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1) if label == "CODE" and match.lastindex else match.group(0)
                start = match.start(1) if label == "CODE" and match.lastindex else match.start()
                end = match.end(1) if label == "CODE" and match.lastindex else match.end()
                if any(not (end <= occupied_start or start >= occupied_end) for occupied_start, occupied_end in occupied_spans):
                    continue
                _append_entity(
                    entities,
                    seen,
                    {
                        "text": value,
                        "label": label,
                        "start": start,
                        "end": end,
                        "score": 1.0,
                        "source": "rule",
                    },
                )
                occupied_spans.append((start, end))

        entities.sort(key=lambda item: (item["start"], item["end"], item["label"]))
        return entities


class GeminiEntityExtractor:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.rule_fallback = RuleEntityExtractor()

    def predict(self, text: str) -> list[dict[str, Any]]:
        prompt = (
            "Extract maintainer-relevant entities from the text.\n"
            "Return a JSON array of objects with keys: text, label, start, end.\n"
            "Use labels such as EMAIL, URL, ISSUE, VERSION, PATH, MENTION, CODE.\n"
            "Return JSON only.\n\n"
            f"Text:\n{text}"
        )
        try:
            response = self.model.generate_content(prompt)
        except Exception:
            return self.rule_fallback.predict(text)

        parsed = _safe_json_loads(response.text)
        if not isinstance(parsed, list):
            return self.rule_fallback.predict(text)

        entities: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        cursor = 0
        for item in parsed:
            if not isinstance(item, dict):
                continue
            entity_text = str(item.get("text") or "").strip()
            label = str(item.get("label") or "").strip().upper()
            if not entity_text or not label:
                continue

            start = item.get("start")
            end = item.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                start = text.find(entity_text, cursor)
                if start < 0:
                    continue
                end = start + len(entity_text)
            cursor = end
            _append_entity(
                entities,
                seen,
                {
                    "text": entity_text,
                    "label": label,
                    "start": start,
                    "end": end,
                    "score": float(item.get("score", 0.85)),
                    "source": "gemini",
                },
            )

        return entities or self.rule_fallback.predict(text)


class RuleSummarizer:
    def predict(self, text: str, max_sentences: int = 3) -> str:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            return ""

        sentence_split = re.split(r"(?<=[.!?])\s+", cleaned)
        sentences = [sentence.strip() for sentence in sentence_split if sentence.strip()]
        if sentences:
            return " ".join(sentences[: max(1, min(max_sentences, 5))])

        return cleaned[:400]


class GeminiSummarizer:
    def __init__(self, api_key, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.rule_fallback = RuleSummarizer()

    def predict(self, text: str, max_sentences: int = 3) -> str:
        prompt = (
            "Summarize the following maintainer note in at most "
            f"{max_sentences} concise sentences.\n"
            "Focus on the root cause, important entities, and the next action.\n"
            "Return plain text only.\n\n"
            f"Text:\n{text}"
        )
        try:
            response = self.model.generate_content(prompt)
        except Exception:
            return self.rule_fallback.predict(text, max_sentences=max_sentences)

        summary = (response.text or "").strip()
        return summary or self.rule_fallback.predict(text, max_sentences=max_sentences)
