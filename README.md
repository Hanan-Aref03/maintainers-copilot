# Maintainer's Copilot

Authenticated chatbot for open-source maintainers - issue classification, entity extraction, RAG over docs plus resolved issues, embeddable widget, and CI-gated evals.

## Architecture

- FastAPI backend with layered architecture (api -> service -> repository -> domain)
- Model server (separate container) for issue classification with Gemini-backed zero/few-shot and a rule fallback
- Postgres + pgvector for long-term semantic memory
- Redis for short-term conversation state
- MinIO for model artifacts and eval reports
- Vault for secrets
- OpenTelemetry + Jaeger for tracing
- Streamlit internal admin console
- React widget (Vite) embeddable via one-line script

## Model Server

The `model-server` container now runs the FastAPI app in `model_server/app/main.py`.
It exposes:

- `GET /health`
- `POST /classify`

It reads `GEMINI_API_KEY` and `GEMINI_MODEL` from `.env` in local development or from Compose environment variables in Docker.
The host port is configurable with `MODEL_SERVER_HOST_PORT` and defaults to `8011` so it avoids collisions on machines where `8001` is already taken.

## Quick Start

```bash
cp .env.example .env
# edit .env with your secrets
docker compose up -d --build
```

## Database Workflow

Run the migration container in a proper Alembic environment:

```bash
docker compose up -d db
docker compose run --rm migrate
```

That container builds with `alembic`, `sqlalchemy`, `psycopg2-binary`, and `pgvector`, so the initial migration can create the `users`, `widgets`, `long_term_memory`, and `audit_logs` tables plus the `vector` extension.

Host-side tools like plain `alembic` or local Python scripts connect to the database container through `DB_HOST_PORT` instead of `5432`, so they do not collide with any Postgres service already running on your machine. The default is `5433`.

To inspect the schema in pgAdmin:

```bash
docker compose up -d pgadmin
```

Open `http://localhost:5050` and sign in with:

- Email: `admin@example.com`
- Password: `pgadmin123`

Add a new server in pgAdmin with:

- Name: `maintainers-db`
- Host: `db`
- Port: `5432`
- Maintenance DB: `maintainers`
- Username: `copilot`
- Password: the value of `DB_PASSWORD` from `.env` or `changeme` if you kept the defaults

Important: this password is for the Postgres server connection, not the pgAdmin login. If you change `DB_PASSWORD`, use the same new value here. If pgAdmin still says `password authentication failed for user "copilot"`, delete and re-add the server entry so it stops using any saved old password.

After you connect, expand `Servers -> maintainers-db -> Databases -> maintainers -> Schemas -> public -> Tables` to see the tables.

If you want the whole infra stack together, you can still use:

```bash
docker compose up -d db redis minio vault jaeger pgadmin migrate
```

`migrate` is a one-shot job, so it exits after applying the schema.

On Windows, Docker Desktop often occupies host port `8000`. This repo now exposes the API on `API_HOST_PORT` and defaults to `8010` so `uvicorn` and Compose can run without colliding with Docker's own backend service. If you want a different port, override `API_HOST_PORT` in `.env`.

If `docker compose run --rm migrate` fails with `password authentication failed for user "copilot"`, your existing `pgdata` volume was initialized with a different `DB_PASSWORD`. In that case, either:

- wipe the local database volume and restart with `.env.example` values, or
- change the `copilot` role password inside the running `db` container to match your current `DB_PASSWORD`

## Vault Bootstrap

Vault secrets are not seeded from Compose.
Run the bootstrap script separately against the target Vault endpoint:

```bash
sh scripts/vault-bootstrap.sh
```

The script loads the repo `.env` automatically, so with the local defaults you can usually run it without exporting anything first. If you want to override values, set them in your shell before running the script. The canonical API key variable is `GEMINI_API_KEY`; `VOYAGE_API_KEY` is accepted as a free fallback, and `OPENAI_API_KEY` is still accepted as a legacy alias for Gemini.

Runtime defaults:

- `GEMINI_MODEL=gemini-2.5-flash` for generation
- `VOYAGE_EMBEDDING_MODEL=voyage-code-2` for retrieval embeddings
- `API_HOST_PORT=8010` for the host-facing API port

Gemini generates the chat response directly. Voyage powers the retrieval context that gets fed into Gemini and also provides a graceful memory-based fallback when Gemini is unavailable.

For production, run that script from a secure admin environment or CI/CD job with access to the Vault cluster.

### Windows PowerShell

If you are on Windows, use the PowerShell script instead of installing `vault.exe` or Chocolatey:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap_vault.ps1
```

The script loads the repo `.env` automatically, so with the local defaults you can usually run it directly. If you want to override values, set them in your shell before running the script. The canonical API key variable is `GEMINI_API_KEY`; `VOYAGE_API_KEY` is accepted as a free fallback, and `OPENAI_API_KEY` is still accepted as a legacy alias for Gemini. The script uses Vault's HTTP API directly, so no local Vault CLI or package manager is required.
