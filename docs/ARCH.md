# Architecture

## System Shape

Maintainers' Copilot uses a layered FastAPI backend plus a separate model server, a React widget bundle, and an internal Streamlit console.

## Main Components

- `app/` - API layer, services, repositories, and infrastructure helpers
- `model_server/` - standalone inference service for classification, NER, and summarization
- `widget/` - embeddable React/Vite client served as a single JS bundle
- `chatbot_streamlit/` - internal admin surface for operators and demos
- `data_pipeline/` - dataset preparation and golden-set generation
- `evals/` - evaluation scripts and thresholds

## Request Flow

1. The host page loads `GET /widgets/widget.js`.
2. The API injects runtime config and serves the widget bundle.
3. The widget calls the public widget chat route with an origin allowlist check.
4. The chat service retrieves short-term memory, long-term memory, and RAG context.
5. The model server handles classifier, NER, and summarizer calls.
6. Long-term writes are recorded with audit entries.

## Data Stores

- Postgres stores users, widgets, long-term memory, and audit logs.
- Redis stores short-term conversation state.
- Vault stores secrets and bootstrap credentials.
- pgvector powers semantic retrieval.

## Observability

- Shared helpers install request IDs, trace IDs, redaction, and FastAPI middleware.
- Logs and payloads are redacted before they leave the application boundary.
- Traces are emitted when OpenTelemetry is available and degrade safely when it is not.

