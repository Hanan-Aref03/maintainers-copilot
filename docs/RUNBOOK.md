# Runbook

## Prerequisites
- Docker Desktop
- Python 3.11+
- Node 18+ for rebuilding the widget bundle
- A populated `.env` file based on `.env.example`

## One-shot Windows Run
Use the helper script to start the full stack, bootstrap Vault, run migrations, launch the API/UI/widget services, and print a Postgres schema snapshot.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_stack.ps1
```

If you want only the services without the Vault bootstrap or the schema snapshot, the script accepts `-SkipVaultBootstrap` and `-SkipDatabaseSnapshot`.

## 1. Create your environment file
Copy the example file and fill in the real secrets.

```bash
cp .env.example .env
```

## 2. Build the widget bundle
Rebuild the widget whenever code under `widget/src/` changes.

```bash
cd widget
npm install
npm run build
cd ..
```

## 3. Start the infrastructure
Bring up the supporting services first.

```bash
docker compose up -d db redis minio vault jaeger pgadmin
```

## 4. Run database migrations
Apply the schema before starting the API.

```bash
docker compose run --rm migrate
```

## 5. Start the application services
Start the model server, API, Streamlit admin app, widget server, and demo host.

```bash
docker compose up -d model-server api streamlit widget host
```

## 6. Check that everything is up
- API health: `http://localhost:8010/health`
- Model server health: `http://localhost:8011/health`
- API docs: `http://localhost:8010/docs`
- Streamlit: `http://localhost:8501`
- Widget: `http://localhost:8080`
- Host demo: `http://localhost:3000`
- pgAdmin: `http://localhost:5050`
- Jaeger: `http://localhost:16686`

## Notes
- Rebuild the widget after any change in `widget/src/`.
- The API defaults to port `8010` to avoid conflicts with local Docker setups.
- Vault secrets are bootstrapped separately.
- If Postgres auth fails, the local volume may still have old credentials.
