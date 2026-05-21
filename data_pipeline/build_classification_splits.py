from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPO_ROOT / "data_pipeline" / "pandas_issues.json"
OUTPUT_PATH = REPO_ROOT / "data_pipeline" / "classification_splits.json"


def _label_from_issue(issue: dict[str, object]) -> str:
    labels = [str(label).lower() for label in (issue.get("labels") or [])]
    if any(label in labels for label in ("bug", "regression")):
        return "bug"
    if any(label in labels for label in ("enhancement", "feature", "new feature")):
        return "feature"
    if any(label in labels for label in ("docs", "documentation")):
        return "docs"
    if any(label in labels for label in ("question", "how-to")):
        return "question"
    return "other"


def _created_at(issue: dict[str, object]) -> datetime:
    raw = str(issue.get("created_at") or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _split_group(rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    total = len(rows)
    train_count = max(1, int(round(total * 0.6)))
    val_count = max(1 if total >= 3 else 0, int(round(total * 0.2)))
    if train_count + val_count >= total:
        overflow = train_count + val_count - (total - 1)
        if overflow > 0:
            take = min(overflow, max(train_count - 1, 0))
            train_count -= take
            overflow -= take
        if overflow > 0:
            val_count -= min(overflow, max(val_count - 1, 0))
    test_count = max(0, total - train_count - val_count)
    if test_count == 0 and total >= 3:
        if val_count > 1:
            val_count -= 1
        elif train_count > 1:
            train_count -= 1
        test_count = total - train_count - val_count

    return {
        "train": rows[:train_count],
        "val": rows[train_count : train_count + val_count],
        "test": rows[train_count + val_count : train_count + val_count + test_count],
    }


def build_splits() -> dict[str, list[dict[str, object]]]:
    with SOURCE_PATH.open(encoding="utf-8") as f:
        issues = json.load(f)

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for issue in issues:
        grouped[_label_from_issue(issue)].append(issue)

    splits = {"train": [], "val": [], "test": []}
    for rows in grouped.values():
        rows = sorted(rows, key=_created_at)
        group_splits = _split_group(rows)
        for split_name in splits:
            splits[split_name].extend(group_splits[split_name])

    for split_name in splits:
        splits[split_name] = sorted(splits[split_name], key=_created_at)
    return splits


if __name__ == "__main__":
    splits = build_splits()
    OUTPUT_PATH.write_text(json.dumps(splits, indent=2), encoding="utf-8")
    print(
        "Saved classification splits:",
        {name: len(items) for name, items in splits.items()},
    )

