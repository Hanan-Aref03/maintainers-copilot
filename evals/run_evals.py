from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from evals.classification_eval import evaluate_classification_models
from evals.rag_eval import evaluate_rag
from app.services.eval_artifact_service import EvalArtifactService

logger = logging.getLogger(__name__)


def _resolve_run_id() -> str:
    for candidate in (
        os.getenv("GITHUB_RUN_ID"),
        os.getenv("GITHUB_SHA"),
        os.getenv("CI_PIPELINE_ID"),
        os.getenv("BUILD_ID"),
    ):
        if candidate:
            return str(candidate).strip().replace("/", "-")
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classification-golden", default="evals/golden_sets/classification_golden.json")
    parser.add_argument("--rag-golden", default="evals/golden_sets/rag_golden.json")
    parser.add_argument("--output", default="evals/eval_report.json")
    args = parser.parse_args()

    classification_report = evaluate_classification_models(args.classification_golden)
    rag_report = asyncio.run(evaluate_rag(args.rag_golden))
    report = {
        "classification": classification_report,
        "rag": rag_report,
    }
    run_id = _resolve_run_id()
    try:
        EvalArtifactService().store_run(
            run_id=run_id,
            combined_report=report,
            classification_report=classification_report,
            rag_report=rag_report,
            metadata={
                "classification_golden": args.classification_golden,
                "rag_golden": args.rag_golden,
                "source": "run_evals.py",
            },
        )
    except Exception as exc:  # pragma: no cover - best-effort artifact mirroring
        logger.warning("Failed to mirror eval artifacts to MinIO: %s", exc)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
