from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8011")
DEFAULT_MODELS = ("rule", "fine", "few")


def _load_golden(golden_set_path: str | Path) -> list[dict[str, object]]:
    with Path(golden_set_path).open(encoding="utf-8") as f:
        return json.load(f)


def _extract_class_report(report: dict[str, object], labels: list[str]) -> dict[str, float]:
    per_class: dict[str, float] = {}
    for label in labels:
        label_report = report.get(label)
        if isinstance(label_report, dict):
            per_class[label] = float(label_report.get("f1-score", 0.0))
    return per_class


def evaluate_classification(golden_set_path: str | Path, model_name: str = "rule") -> dict[str, object]:
    golden = _load_golden(golden_set_path)

    y_true: list[str] = []
    y_pred: list[str] = []
    errors: list[dict[str, str]] = []
    fallback_items: list[dict[str, object]] = []

    for item in golden:
        response = requests.post(
            f"{MODEL_SERVER_URL}/classify",
            json={
                "title": item["title"],
                "body": item["body"],
                "model": model_name,
            },
            timeout=120,
        )
        if response.status_code != 200:
            errors.append(
                {
                    "id": str(item.get("id")),
                    "error": response.text,
                }
            )
            continue

        payload = response.json()
        pred = str(payload["label"])
        used_fallback = bool(payload.get("used_fallback", False))
        y_true.append(str(item["true_label"]))
        y_pred.append(pred)
        if used_fallback:
            fallback_items.append(
                {
                    "id": item.get("id"),
                    "model": model_name,
                    "classifier_source": payload.get("classifier_source"),
                    "fallback_reason": payload.get("fallback_reason"),
                }
            )

    labels = sorted({label for label in y_true})
    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0) if y_true else {}
    matrix = confusion_matrix(y_true, y_pred, labels=labels).tolist() if labels else []

    return {
        "model": model_name,
        "accuracy": float(accuracy_score(y_true, y_pred)) if y_true else 0.0,
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)) if y_true else 0.0,
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)) if y_true else 0.0,
        "per_class_f1": _extract_class_report(report, labels),
        "confusion_matrix": matrix,
        "labels": labels,
        "num_samples": len(y_true),
        "failed_items": errors,
        "fallback_count": len(fallback_items),
        "fallback_rate": (len(fallback_items) / len(y_true)) if y_true else 0.0,
        "fallback_items": fallback_items,
    }


def evaluate_classification_models(
    golden_set_path: str | Path,
    models: tuple[str, ...] = DEFAULT_MODELS,
) -> dict[str, object]:
    results = {model: evaluate_classification(golden_set_path, model) for model in models}
    return {
        "models": results,
        "golden_set_path": str(golden_set_path),
        "num_models": len(models),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="evals/golden_sets/classification_golden.json")
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    parser.add_argument("--output", default="evals/classification_report.json")
    args = parser.parse_args()

    report = evaluate_classification_models(args.golden, tuple(args.models))
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
