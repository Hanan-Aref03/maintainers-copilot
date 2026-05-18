# Maintainer's Copilot

Authenticated chatbot for open‑source maintainers – issue classification, entity extraction, RAG over docs + resolved issues, embeddable widget, and CI‑gated evals.

## Architecture

- **FastAPI** backend with layered architecture (api → service → repository → domain)
- **Model server** (separate container) for classifier/NER/summarizer
- **Postgres + pgvector** for long‑term semantic memory
- **Redis** for short‑term conversation state
- **MinIO** for model artifacts & eval reports
- **Vault** for secrets
- **OpenTelemetry + Jaeger** for tracing
- **Streamlit** internal admin console
- **React widget** (Vite) embeddable via one‑line script

## Quick Start

```bash
cp .env.example .env
# edit .env with your secrets
docker compose up -d