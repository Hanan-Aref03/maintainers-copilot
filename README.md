# Maintainer's Copilot

Authenticated chatbot for open-source maintainers - issue classification, entity extraction, RAG over docs plus resolved issues, embeddable widget, and CI-gated evals.

## Architecture

- FastAPI backend with layered architecture (api -> service -> repository -> domain)
- Model server (separate container) for classifier/NER/summarizer
- Postgres + pgvector for long-term semantic memory
- Redis for short-term conversation state
- MinIO for model artifacts and eval reports
- Vault for secrets
- OpenTelemetry + Jaeger for tracing
- Streamlit internal admin console
- React widget (Vite) embeddable via one-line script

## Quick Start

```bash
cp .env.example .env
# edit .env with your secrets
docker compose up -d --build
```

## Vault Bootstrap

Vault secrets are not seeded from Compose.
Run the bootstrap script separately against the target Vault endpoint:

```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=devroot
export JWT_SECRET=replace-with-a-real-secret
export OPENAI_API_KEY=replace-with-a-real-openai-key
export DB_PASSWORD=replace-with-a-real-db-password
export MINIO_ROOT_USER=replace-with-a-real-minio-access-key
export MINIO_ROOT_PASSWORD=replace-with-a-real-minio-secret-key
export GITHUB_TOKEN=replace-with-a-real-github-token

sh scripts/vault-bootstrap.sh
```

For production, run that script from a secure admin environment or CI/CD job with access to the Vault cluster.
