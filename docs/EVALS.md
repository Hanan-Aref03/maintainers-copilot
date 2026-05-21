# Evaluations

## Datasets

- Classification golden set: 25 hand-curated issues
- RAG golden set: 25 question/answer pairs
- Training split source: labeled issues from `data_pipeline/pandas_issues.json`

## Classification Metrics

- Accuracy
- Macro F1
- Weighted F1
- Per-class F1
- Confusion matrix
- Fallback count and fallback rate

## RAG Metrics

- hit@5
- MRR@10
- Faithfulness
- Answer relevancy
- Actual end-to-end chat answers against the golden set
- RAGAS-backed judge scoring for faithfulness and answer relevancy
- Fallback count and fallback rate for assistant responses

## Scripts

- `python data_pipeline/build_classification_splits.py`
- `python data_pipeline/create_rag_golden.py`
- `python evals/classification_eval.py`
- `python evals/rag_eval.py`
- `python evals/run_evals.py`

## Reporting

The combined runner writes `evals/eval_report.json`, and the per-task scripts emit JSON reports for submission.
`evals/rag_eval.py` now evaluates the real chat path, not just retrieval, and includes `ragas_status` plus fallback metadata in the report.
