from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from uuid import UUID

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.infra.ai_clients import GeminiClient
from app.services.chat_service import ChatService
from evals.ragas_support import (
    GeminiRagasEmbeddings,
    build_ragas_metrics,
    build_ragas_llm,
)

EVAL_USER_ID = UUID("00000000-0000-0000-0000-000000000000")


def _load_golden(golden_path: str | Path) -> list[dict[str, object]]:
    with Path(golden_path).open(encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _f1_overlap(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    overlap = left_set & right_set
    precision = len(overlap) / len(left_set)
    recall = len(overlap) / len(right_set)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _doc_text(doc: dict[str, object]) -> str:
    title = str(doc.get("title") or "").strip()
    body = str(doc.get("body") or "").strip()
    return "\n".join(part for part in [title, body] if part).strip()


def _fallback_faithfulness(response: str, retrieved_contexts: list[str]) -> float:
    context_text = " ".join(retrieved_contexts)
    return _f1_overlap(response, context_text)


def _fallback_answer_relevancy(response: str, reference_answer: str, question: str) -> float:
    if reference_answer.strip():
        return _f1_overlap(response, reference_answer)
    return _f1_overlap(response, question)


async def _chat_turn(chat_service: ChatService, item: dict[str, object], index: int) -> dict[str, object]:
    question = str(item["question"])
    reference_answer = str(item.get("answer") or "")
    ground_truth_doc_id = item["ground_truth_doc_id"]
    thread_id = f"rag-eval-{index}"

    if hasattr(chat_service, "process_message_with_metadata"):
        result = await chat_service.process_message_with_metadata(
            user_id=EVAL_USER_ID,
            thread_id=thread_id,
            message=question,
        )
    else:
        response_text = await chat_service.process_message(
            user_id=EVAL_USER_ID,
            thread_id=thread_id,
            message=question,
        )
        result = {
            "response": response_text,
            "used_fallback": False,
            "llm_provider": "unknown",
            "retrieved_doc_ids": [],
            "retrieved_contexts": [],
        }

    response = str(result.get("response") or "")
    retrieved_doc_ids = [doc_id for doc_id in result.get("retrieved_doc_ids") or []]
    retrieved_contexts = [str(context).strip() for context in result.get("retrieved_contexts") or [] if str(context).strip()]
    used_fallback = bool(result.get("used_fallback", False))
    llm_provider = str(result.get("llm_provider") or "unknown")

    hit_rank = next(
        (
            idx + 1
            for idx, doc_id in enumerate(retrieved_doc_ids[:10])
            if str(doc_id) == str(ground_truth_doc_id)
        ),
        None,
    )

    return {
        "question": question,
        "response": response,
        "reference_answer": reference_answer,
        "ground_truth_doc_id": ground_truth_doc_id,
        "retrieved_doc_ids": retrieved_doc_ids,
        "retrieved_contexts": retrieved_contexts,
        "hit_rank": hit_rank,
        "used_fallback": used_fallback,
        "llm_provider": llm_provider,
        "fallback_reason": result.get("fallback_reason"),
    }


async def evaluate_rag(golden_path: str | Path, k: int = 5) -> dict[str, object]:
    golden = _load_golden(golden_path)
    chat_service = ChatService(db=None)

    turns = [await _chat_turn(chat_service, item, index) for index, item in enumerate(golden)]

    hits = 0
    reciprocal_ranks: list[float] = []
    fallback_count = 0
    example_reports = []
    faithfulness_scores: list[float] = []
    answer_relevancy_scores: list[float] = []

    for turn in turns:
        hit_rank = turn["hit_rank"]
        if hit_rank is not None:
            reciprocal_ranks.append(1.0 / hit_rank)
            if hit_rank <= k:
                hits += 1
        else:
            reciprocal_ranks.append(0.0)

        fallback_count += int(bool(turn["used_fallback"]))
        example_reports.append(
            {
                "question": turn["question"],
                "response": turn["response"],
                "reference_answer": turn["reference_answer"],
                "ground_truth_doc_id": turn["ground_truth_doc_id"],
                "retrieved_ids": [doc_id for doc_id in turn["retrieved_doc_ids"][:k]],
                "hit_rank": hit_rank,
                "used_fallback": turn["used_fallback"],
                "llm_provider": turn["llm_provider"],
                "fallback_reason": turn["fallback_reason"],
            }
        )

    total = len(turns) or 1
    report: dict[str, object] = {
        "hit_at_5": hits / total,
        "mrr_at_10": sum(reciprocal_ranks) / total,
        "num_samples": len(turns),
        "golden_set_path": str(golden_path),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_count / total,
        "examples": example_reports,
        "ragas_status": "unavailable",
    }

    try:
        gemini_client = GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.provider_timeout_seconds,
        )
        ragas_llm = build_ragas_llm(settings.gemini_model)
        ragas_embeddings = GeminiRagasEmbeddings(gemini_client)
        metrics = build_ragas_metrics(ragas_llm, ragas_embeddings)
        faithfulness_metric, answer_relevancy_metric = metrics

        for turn in turns:
            retrieved_contexts = turn["retrieved_contexts"] or [turn["reference_answer"] or turn["question"]]
            faithfulness_result = await faithfulness_metric.ascore(
                user_input=turn["question"],
                response=turn["response"],
                retrieved_contexts=retrieved_contexts,
            )
            answer_relevancy_result = await answer_relevancy_metric.ascore(
                user_input=turn["question"],
                response=turn["response"],
            )
            faithfulness_scores.append(float(faithfulness_result.value))
            answer_relevancy_scores.append(float(answer_relevancy_result.value))

        report["faithfulness"] = sum(faithfulness_scores) / total
        report["answer_relevancy"] = sum(answer_relevancy_scores) / total
        report["ragas_status"] = "ok"
    except Exception as exc:
        report["ragas_error"] = str(exc)
        report["faithfulness"] = sum(
            _fallback_faithfulness(turn["response"], turn["retrieved_contexts"])
            for turn in turns
        ) / total
        report["answer_relevancy"] = sum(
            _fallback_answer_relevancy(turn["response"], turn["reference_answer"], turn["question"])
            for turn in turns
        ) / total
        report["ragas_status"] = "heuristic_fallback"

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="evals/golden_sets/rag_golden.json")
    parser.add_argument("--output", default="evals/rag_report.json")
    args = parser.parse_args()

    report = asyncio.run(evaluate_rag(args.golden))
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
