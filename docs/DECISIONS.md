# Decisions

## 1. Separate model server

We keep inference in `model_server/` so the API can stay stable while the model stack changes independently.

## 2. JWT auth with token versioning

Authentication uses JWTs plus a token-version field so sessions can be revoked without rotating every secret.

## 3. Redis for short-term memory

Conversation turn state stays in Redis because it is ephemeral and fast to read/write.

## 4. Postgres + pgvector for long-term memory

Persistent memory lives in Postgres so it can be audited, queried, and vector-searched alongside the core app data.

## 5. Hybrid retrieval

RAG uses BM25 plus embeddings and reranking so the system works even when the embedding provider is unavailable.

## 6. Fine-tuned local classifier artifact

The "fine" classifier is trained from the labeled issues in the repo and saved as a local artifact so demo runs are repeatable.

## 7. Public widget chat route

The widget needs a no-auth chat route with origin allowlisting so the embedded demo can work in a browser without exposing the admin API.

## 8. Shared observability and redaction

Tracing and redaction live in `shared/` so both the API and model server enforce the same safe logging behavior.

