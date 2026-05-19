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

## Database Workflow

Run the migration container in a proper Alembic environment:

```bash
docker compose up -d db
docker compose run --rm migrate
```

That container builds with `alembic`, `sqlalchemy`, `psycopg2-binary`, and `pgvector`, so the initial migration can create the `users`, `widgets`, `long_term_memory`, and `audit_logs` tables plus the `vector` extension.

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

After you connect, expand `Servers -> maintainers-db -> Databases -> maintainers -> Schemas -> public -> Tables` to see the tables.

If you want the whole infra stack together, you can still use:

```bash
docker compose up -d db redis minio vault jaeger pgadmin migrate
```

`migrate` is a one-shot job, so it exits after applying the schema.

If `docker compose run --rm migrate` fails with `password authentication failed for user "copilot"`, your existing `pgdata` volume was initialized with a different `DB_PASSWORD`. In that case, either:

- wipe the local database volume and restart with `.env.example` values, or
- change the `copilot` role password inside the running `db` container to match your current `DB_PASSWORD`

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

### Windows PowerShell

If you are on Windows, use the PowerShell script instead of installing `vault.exe` or Chocolatey:

```powershell
$env:VAULT_ADDR="http://localhost:8200"
$env:VAULT_TOKEN="devroot"
$env:JWT_SECRET="replace-with-a-real-secret"
$env:OPENAI_API_KEY="replace-with-a-real-openai-key"
$env:DB_PASSWORD="replace-with-a-real-db-password"
$env:MINIO_ROOT_USER="replace-with-a-real-minio-access-key"
$env:MINIO_ROOT_PASSWORD="replace-with-a-real-minio-secret-key"
$env:GITHUB_TOKEN="replace-with-a-real-github-token"

powershell -ExecutionPolicy Bypass -File scripts/bootstrap_vault.ps1
```

The script uses Vault's HTTP API directly, so no local Vault CLI or package manager is required.
