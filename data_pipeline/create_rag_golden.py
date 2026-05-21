from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
KB_PATH = REPO_ROOT / "data_pipeline" / "knowledge_base.json"
OUTPUT_PATH = REPO_ROOT / "evals" / "golden_sets" / "rag_golden.json"


def _clean_text(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<img[^>]*>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _first_sentences(text: str, limit: int = 2) -> str:
    sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", _clean_text(text)) if segment.strip()]
    if not sentences:
        return _clean_text(text)[:280]
    return " ".join(sentences[:limit])[:500]


def _question_from_issue(item: dict[str, str]) -> str:
    title = str(item.get("title") or "").strip()
    lower = title.lower()
    if lower.startswith("bug:") or "bug:" in lower or "bug " in lower:
        return f"What bug does {title} describe?"
    if lower.startswith("enh:") or "enh:" in lower or "feature" in lower:
        return f"What feature request is described in {title}?"
    if lower.startswith("doc:") or "doc:" in lower or "documentation" in lower:
        return f"What documentation change is described in {title}?"
    if "perf" in lower or "performance" in lower:
        return f"What performance issue is described in {title}?"
    return f"What issue is discussed in {title}?"


def build_rag_golden() -> list[dict[str, str]]:
    with KB_PATH.open(encoding="utf-8") as f:
        kb = json.load(f)

    golden: list[dict[str, str]] = []
    for item in kb[:25]:
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        answer = _first_sentences(f"{title}. {body}", limit=2)
        golden.append(
            {
                "question": _question_from_issue(item),
                "answer": answer,
                "ground_truth_doc_id": item["id"],
                "ground_truth_chunks": [title, _clean_text(body)[:800]],
                "context": f"{title}\n{_clean_text(body)[:1000]}",
            }
        )
    return golden


if __name__ == "__main__":
    golden = build_rag_golden()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(golden, f, indent=2)
    print(f"Saved {len(golden)} RAG golden QA pairs")

