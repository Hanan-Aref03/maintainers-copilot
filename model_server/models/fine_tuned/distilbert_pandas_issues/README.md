# DistilBERT pandas issue classifier

This folder is the landing zone for the fine-tuned transformer classifier produced by [notebooks/pandas_distilbert_issue_classifier.ipynb](../../../../notebooks/pandas_distilbert_issue_classifier.ipynb).

## Expected artifacts

- `config.json`
- `model.safetensors` or `pytorch_model.bin`
- `tokenizer.json`
- `tokenizer_config.json`
- `special_tokens_map.json`
- `label_map.json`
- `metrics.json`
- `training_summary.json`
- `eda_overview.png`
- `confusion_matrix.png`

## What it is for

- Train a DL classifier on `pandas-dev/pandas` issues with DistilBERT.
- Keep the saved model separate from the classical TF-IDF classifier.
- Make it easy to wire the transformer into the model server later if you want a `model=dl` path.

## Notes

- The notebook uses the repo's cached `data_pipeline/pandas_issues.json` when available.
- If the cache is missing, it falls back to GitHub API fetches.
- The repository keeps the classical model and transformer model in separate folders on purpose.
