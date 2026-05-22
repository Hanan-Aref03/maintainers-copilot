# Maintainer's Copilot Code Explainer

This document explains how the repository works at two levels:

- a high-level product and architecture view
- a deeper technical walkthrough of how requests, data, models, and UI pieces interact

It is written to help a new maintainer understand the system end to end without having to read every file first.

## 1. What The Project Does

Maintainer's Copilot is an authenticated assistant for open-source maintainers. It combines:

- an API for auth, chat, memory, and widget management
- a separate model server for classification, entity extraction, and summarization
- a React widget that can be embedded on a host page
- a Streamlit operator console for demos and internal administration
- Postgres, Redis, Minio, Vault, and Jaeger for storage, cache, secret management, and tracing

The goal is to give maintainers a single place to:

- classify issues
- search and reuse long-term memory
- ask questions against repository knowledge
- configure a public embeddable widget
- inspect the system with a human-friendly admin surface

## 2. Architecture At A Glance

```text
Browser / Host Page
    |-- loads widget.js from API
    |-- talks to /widgets/{id}/chat

Streamlit Admin UI
    |-- talks to API for auth, chat, memory, widgets
    |-- talks to model server for classification / NER / summarization

FastAPI API
    |-- auth
    |-- chat orchestration
    |-- memory persistence
    |-- widget CRUD + widget JS loader
    |-- Vault loading + tracing + redaction

Model Server
    |-- rule classifier
    |-- fine-tuned classifier
    |-- Gemini zero-shot / few-shot paths
    |-- rule NER and summarizer

Data / Infra
    |-- Postgres for users, widgets, long-term memory, audit logs
    |-- Redis for short-term conversation memory
    |-- Vault for secrets
    |-- Minio for object storage
    |-- Jaeger / OTLP for traces
```

The code is intentionally split so that the API can orchestrate product behavior while the model server isolates model-specific dependencies.

## 3. Repository Map

The main folders and their responsibilities are:

- `app/` - API layer, services, repositories, infra, and domain models
- `model_server/` - standalone model endpoints
- `chatbot_streamlit/` - internal operator dashboard
- `widget/` - embeddable React client
- `data_pipeline/` - dataset prep and knowledge base generation
- `evals/` - classification and RAG evaluation scripts
- `migrations/` - schema migrations
- `shared/` - observability helpers shared by services
- `scripts/` - bootstrap and run helpers
- `docs/` - architecture, decisions, runbook, security, and this explainer

## 4. How A User Request Flows

### 4.1 Widget Chat Flow

1. A host page includes the widget script from `GET /widgets/widget.js?widget_id=<public_id>`.
2. The API looks up the widget, injects runtime config into the bundle, and enforces the widget's origin allow-list.
3. The widget opens a compact chat panel and posts user messages to `POST /widgets/{public_id}/chat`.
4. The API validates the widget, resolves the widget owner, and routes the message into `ChatService`.
5. `ChatService` combines:
   - recent conversation turns from Redis
   - long-term memory from Postgres
   - RAG context from the knowledge base
   - an LLM answer from Gemini when available
6. If Gemini is unavailable, the service uses a local fallback reply and returns explicit metadata saying so.

### 4.2 Streamlit Operator Flow

1. The user signs in or registers in the Streamlit app.
2. Streamlit stores the issued access token in session state.
3. The user can:
   - chat with the assistant
   - inspect and write memory
   - create or inspect widgets
   - run classifier / NER / summarization tools
4. The UI queries the API and model server directly and renders the result with metadata so fallback behavior stays visible.

### 4.3 Auth Flow

1. `POST /auth/register` or `POST /auth/login` creates the session.
2. Passwords are hashed before storage.
3. JWTs carry token-version state so sessions can be invalidated later.
4. Role checks gate admin-only widget operations.

### 4.4 Model Tool Flow

The Streamlit tools tab talks directly to the model server:

- `/classify` for issue labeling
- `/ner` for entity extraction
- `/summarize` for issue condensation

The model server returns metadata such as `used_fallback`, `classifier_source`, and `fallback_reason` so the UI can show when a local fallback handled a request.

## 5. Data Model

The database schema is intentionally small and opinionated:

- `users`
  - identity, email, password hash, role, token version, timestamps
- `widgets`
  - public widget IDs, owner IDs, theme, greeting, allowed origins, enabled tools
- `long_term_memory`
  - memory entries, memory type, text content, optional embedding, metadata JSON
- `audit_logs`
  - who did what, to what target, and with which details
- `alembic_version`
  - migration bookkeeping

The relationships are straightforward:

- `widgets.owner_id -> users.id`
- `long_term_memory.user_id -> users.id`
- `audit_logs.actor_id -> users.id`

This makes the data easy to explain in demos and easy to inspect in pgAdmin.

## 6. Deep Technical Walkthrough

### 6.1 Configuration And Secrets

Configuration lives in `app/core/config.py`.

The settings layer reads values in this order:

1. environment variables
2. values from a local `.env` file
3. hard-coded defaults

This keeps local development easy while still allowing Vault to inject real runtime secrets in deployed or semi-managed environments.

`app/main.py` also loads Vault secrets at startup through `VaultClient`.

Important behavior:

- Vault secrets are loaded into environment variables when available
- if Vault is down, the app falls back to local settings
- the app never assumes Vault is mandatory for local development

### 6.2 Observability And Redaction

`shared/observability.py` is the central instrumentation layer.

It does four important jobs:

- generates a request ID for each HTTP request
- propagates a trace ID when tracing is enabled
- installs OpenTelemetry spans when the OTLP exporter is available
- redacts secret-like values from logs, spans, and structured payloads

This means:

- API requests can be traced end to end in Jaeger
- logs can be correlated by request ID and trace ID
- credentials and token-like values do not leak into logs by accident

### 6.3 API Layer

`app/main.py` is the API entrypoint.

At startup it:

- loads Vault secrets
- bootstraps demo data when enabled
- configures CORS
- registers the auth, chat, widget, and memory routers

The API is responsible for orchestration, not heavy AI logic. It keeps the product boundary clean:

- auth and session management
- chat routing and widget chat
- widget CRUD
- memory persistence
- health reporting

### 6.4 Chat Service

`app/services/chat_service.py` is the main orchestration layer for assistant replies.

What it does:

1. trims and validates the incoming message
2. optionally embeds the query with the Voyage client
3. loads short-term conversation state from Redis
4. loads long-term memories from Postgres
5. retrieves repository context through RAG
6. ranks memories if embeddings exist
7. builds a single prompt that merges all the context
8. calls Gemini when available
9. falls back to a local reply if the provider is unavailable
10. stores the new turns back into Redis
11. returns metadata for UI and eval visibility

The important design choice here is that chat is not just "LLM in, LLM out". It is a context assembly pipeline:

- short-term memory = recent conversation
- long-term memory = durable user-specific notes
- RAG = issue and documentation context
- fallback = offline resilience with explicit metadata

### 6.5 Long-Term Memory

`LongTermMemory` rows store:

- memory type: `semantic`, `episodic`, or `procedural`
- text content
- optional embedding vector
- metadata JSON

The chat service ranks memories by cosine similarity when embeddings are available. If no query embedding exists, it still returns the top stored memories as a reasonable fallback.

This makes the memory system useful in both online and degraded scenarios.

### 6.6 RAG Pipeline

`app/services/rag_service.py` implements the retrieval stack.

It uses several layers:

- query rewriting
- sparse BM25 retrieval
- dense embedding retrieval
- score blending
- optional cross-encoder reranking

How it works:

1. The original question is optionally rewritten into search-oriented queries.
2. BM25 scores all documents from the knowledge base.
3. Dense embeddings are generated when the provider is available.
4. Sparse and dense scores are blended into a hybrid ranking.
5. A cross-encoder reranker refines the top candidates when its model is available locally.
6. The top documents are returned to the chat service.

Why this matters:

- BM25 gives strong lexical matching
- embeddings help semantic matching
- reranking improves precision at the top
- query rewriting improves recall when the user asks a vague question

The pipeline is also defensive:

- if embeddings are unavailable, it falls back to sparse retrieval
- if the reranker model is not present locally, it skips reranking instead of failing
- trace spans are emitted around rewrite, retrieve, and rerank stages

### 6.7 Model Server

`model_server/app/main.py` exposes the AI endpoints used by the rest of the system.

The server provides:

- rule-based classification
- fine-tuned classification
- Gemini zero-shot and few-shot classification
- rule NER
- Gemini NER
- rule summarization
- Gemini summarization

The key design point is that every classification path returns metadata. That metadata is surfaced to the UI and evaluation scripts so fallback behavior is visible instead of hidden.

`model_server/app/classifiers.py` contains:

- the rule baseline
- the fine-tuned TF-IDF + logistic regression pipeline
- the Gemini-backed classifier wrappers
- the entity extractor and summarizer implementations

### 6.8 Widget Runtime

The widget is a separate React bundle in `widget/`.

At runtime:

- the API injects widget config into `window.__COPILOT_WIDGET_CONFIG__`
- the React app reads the config and detects its widget ID
- the widget renders a floating launcher and panel
- user messages are sent to `/widgets/{id}/chat`
- the widget shows metadata such as provider and retrieved sources

This separation is important because the widget can be embedded anywhere while the actual business logic stays in the API.

The API also enforces:

- public widget ID lookup
- allowed-origin checks
- bundle presence checks

That keeps the public embed surface from turning into an open relay.

### 6.9 Streamlit Console

`chatbot_streamlit/app.py` is the internal admin surface.

It is designed like an operator dashboard, not a toy chat demo.

It includes:

- a service health overview
- auth forms
- a multi-thread chat workspace
- memory inspection and memory writing
- widget creation and widget embed snippets
- model tool execution panels

The Streamlit app keeps its own local state in `st.session_state`, which is the right tradeoff here because it is a demo/admin tool and not a multi-user production frontend.

The UI also probes:

- the API
- the model server
- Vault

That gives immediate visibility into whether the stack is healthy before a demo starts.

### 6.10 Security Model

The security model is layered:

- `.env` is ignored from git
- Vault is the preferred secret source
- logs are redacted
- widget origins are allow-listed
- admin-only routes require role checks
- long-term memory writes are audited

The point is not perfect cryptographic isolation. The point is to keep the local/demo system safe enough that secrets and private payloads do not accidentally leak into logs or browser-visible config.

## 7. End-To-End Example

Here is what happens when a maintainer uses the widget:

1. The host page loads the widget bundle from the API.
2. The API injects widget config and validates the widget ID.
3. The user asks a question in the widget panel.
4. The widget posts the question to the widget chat endpoint.
5. The API validates the origin and resolves the widget owner.
6. `ChatService` assembles:
   - recent chat turns from Redis
   - long-term memories from Postgres
   - retrieved repo context from the RAG service
7. The service calls Gemini if possible.
8. If Gemini is unavailable, it returns a local fallback reply and says so explicitly.
9. The assistant response is redacted and stored in Redis as the next conversation turn.
10. The UI shows the response plus metadata about provider/fallback and retrieved sources.

That same pattern applies in Streamlit, except the admin console exposes more controls and more diagnostics.

## 8. Why The Project Is Structured This Way

The architecture is split to make the system easier to reason about:

- the API handles product orchestration
- the model server owns model-specific dependencies and failure modes
- the widget is a small embed artifact that can be dropped into a host page
- Streamlit is a fast internal console for demos and operations
- Postgres, Redis, Vault, and Jaeger each do one job well

This gives you:

- clearer separation of concerns
- easier local development
- better demo reliability
- safer secret handling
- more explainable evaluation results

## 9. Evaluation And Demo Story

The repo includes deterministic evaluation scripts in `evals/`.

Those scripts help answer:

- how good is the classifier?
- is the retriever finding relevant context?
- are we falling back too often?
- is the answer grounded in retrieved content?

The current setup deliberately surfaces fallback behavior so the reported scores are honest. That is useful because it shows whether the app is truly using the intended model path or falling back to local logic.

## 10. How To Run It

One-shot startup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_full_stack.ps1
```

Direct Streamlit launch:

```powershell
streamlit run chatbot_streamlit/app.py --server.address 0.0.0.0 --server.port 8501
```

Widget development:

```powershell
cd widget
npm install
npm run dev
```

Widget production build:

```powershell
cd widget
npm run build
```

## 11. Short Version

If you need a one-sentence summary:

Maintainer's Copilot is a layered maintainer assistant where the API orchestrates auth, chat, memory, and widgets; the model server handles classification and generation; the widget provides an embeddable public surface; and the Streamlit app provides a clear operator console over the whole system.
