# Maintainer's Copilot

Authenticated assistant for open-source maintainers with issue classification, entity extraction, RAG over docs plus resolved issues, embeddable widget support, and demo/admin tooling.

## Project Docs

- [Architecture](docs/ARCH.md)
- [Decisions](docs/DECISIONS.md)
- [Runbook](docs/RUNBOOK.md)
- [Evaluations](docs/EVALS.md)
- [Security](docs/SECURITY.md)

## What Is Included

- FastAPI backend with layered `api -> service -> repository -> domain` structure
- Separate model server for classification, NER, and summarization
- Redis short-term memory and Postgres + pgvector long-term memory
- Vault-backed secret bootstrap and request/payload redaction
- Streamlit admin console for operators and demos
- React widget bundle served from the API and host demo
- Deterministic evaluation scripts and golden sets

## Quick Start

```bash
cp .env.example .env
docker compose up -d --build
```

If you change the widget source, rebuild the bundle before serving the widget script:

```bash
cd widget
npm run build
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

