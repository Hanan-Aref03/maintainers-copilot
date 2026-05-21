from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from evals.classification_eval import evaluate_classification_models
from evals.rag_eval import evaluate_rag


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
    output_path = Path(args.output)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
