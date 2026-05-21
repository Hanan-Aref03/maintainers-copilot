# Maintainers' Copilot Reference

## What This Project Is
Maintainers' Copilot is a FastAPI-based assistant for open-source maintainers. It is meant to help with issue classification, entity extraction, retrieval over project knowledge, maintainable chat memory, and an embeddable widget for other apps.

## Main Pieces
- `app/` - backend API, services, repositories, and infrastructure helpers
- `model_server/` - small FastAPI service for issue classification
- `widget/` - React/Vite widget bundle that is served to host apps
- `data_pipeline/` - scripts for building the knowledge base and eval data
- `evals/` - evaluation scripts and threshold config
- `docker-compose.yml` - local stack for Postgres, Redis, MinIO, Vault, Jaeger, API, model server, Streamlit, widget, and host

## Basic Flow
1. A client sends a chat request to `POST /chat/`.
2. The backend loads relevant memory and builds a prompt.
3. If Gemini is available, the chat service generates the reply.
4. The response is stored as long-term memory when a database session exists.

## Important Notes
- Short-term memory uses Redis.
- Long-term memory and audit logs use Postgres.
- The model server currently exposes `GET /health` and `POST /classify`.
- Tracing is wired in startup, but the tracing implementation is still a stub.
- Auth is currently a simplified dev flow, not a full JWT signup/login system.

## Good Entry Files
- `app/main.py`
- `app/services/chat_service.py`
- `app/services/rag_service.py`
- `app/infra/database.py`
- `model_server/app/main.py`
- `widget/src/App.jsx`
