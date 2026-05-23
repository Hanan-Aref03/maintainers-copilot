# Maintainer's Copilot

Authenticated assistant for open-source maintainers with issue classification, entity extraction, RAG over docs plus resolved issues, embeddable widget support, and demo/admin tooling.

## What Is Included

- FastAPI backend with layered `api -> service -> repository -> domain` structure
- Separate model server for classification, NER, and summarization
- Redis short-term memory and Postgres + pgvector long-term memory
- Vault-backed secret bootstrap and request/payload redaction
- MinIO-backed file attachments with Postgres metadata and Streamlit download controls
- Structured MinIO buckets for model artifacts, eval runs, and conversation snapshots
- Streamlit admin console with an embedded host-page widget preview
- React widget bundle served from the API and host demo
- Deterministic evaluation scripts and golden sets
- DistilBERT fine-tuning notebook for `pandas-dev/pandas` issues
- Local docs live in `docs/` and are ignored from GitHub so they stay workspace-only.

## Quick Start

```bash
cp .env.example .env
docker compose up -d --build
```

For a one-shot Windows startup that also bootstraps Vault and prints the Postgres schema snapshot, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_stack.ps1
```

If you change the widget source, rebuild the bundle before serving the widget script:

```bash
cd widget
npm run build
```

To work on the transformer classifier, open:

```text
notebooks/pandas_distilbert_issue_classifier.ipynb
```

The notebook writes its artifacts to:

```text
model_server/models/fine_tuned/distilbert_pandas_issues/
```

To run the interfaces directly during local UI work:

```powershell
streamlit run chatbot_streamlit/app.py --server.address 0.0.0.0 --server.port 8501
cd widget
npm install
npm run dev
```

## Verification

Run the test suite:

```bash
python -m pytest -q
```

Run the dataset prep and evaluation scripts:

```bash
python data_pipeline/build_classification_splits.py
python data_pipeline/create_rag_golden.py
python evals/run_evals.py
```

## Vault Bootstrap

Secrets are loaded from Vault when available. For local development, use `.env` and keep it out of git.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_vault.ps1
```

The bootstrap scripts read the repo `.env` automatically and populate Vault with the current local values.

