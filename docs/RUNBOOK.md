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

## Standalone UI Commands
Use these when you want to work on just the front-end surfaces.

```powershell
streamlit run chatbot_streamlit/app.py --server.address 0.0.0.0 --server.port 8501
```

The Widgets tab embeds the host demo page in an iframe so you can see the floating assistant inside a product-like shell.

The Attachments tab is the MinIO-backed file console. Use it to upload a file, inspect the metadata stored in Postgres, and download the object back through the API.

MinIO is split into dedicated buckets so artifact families stay separate:

- `copilot-attachments` for user uploads
- `copilot-model-artifacts` for classifier manifests and binaries
- `copilot-eval-artifacts` for CI eval reports
- `copilot-conversation-snapshots` for recent chat retrieval snapshots

```powershell
cd widget
npm install
npm run dev
```

## Transformer Notebook

Use this notebook to train the DistilBERT issue classifier on `pandas-dev/pandas`:

```text
notebooks/pandas_distilbert_issue_classifier.ipynb
```

It saves the resulting artifacts to:

```text
model_server/models/fine_tuned/distilbert_pandas_issues/
```

When you are ready to ship the widget bundle for Docker, rebuild it with:

```powershell
cd widget
npm run build
```

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
- MinIO API: `http://localhost:9000`
- MinIO console: `http://localhost:9001`
- pgAdmin: `http://localhost:5050`
- Jaeger: `http://localhost:16686`

## Notes
- Rebuild the widget after any change in `widget/src/`.
- The API defaults to port `8010` to avoid conflicts with local Docker setups.
- Vault secrets are bootstrapped separately.
- Attachment blobs live in the `copilot-attachments` MinIO bucket by default.
- Model artifacts, eval reports, and conversation snapshots each have their own bucket.
- Use the MinIO root credentials from `.env` or the Vault bootstrap scripts to sign in to the MinIO console.
- If Postgres auth fails, the local volume may still have old credentials.
