# Requirements Check Against `AIE_Week7_Maintainers_Copilot_v4.pdf`

## Summary

The repo now implements the full demo-oriented stack described in the PDF: JWT auth, model server tools, Redis memory, Postgres + pgvector memory, widget delivery, Streamlit admin, tracing/redaction, evaluation scripts, and Vault-backed secret handling.

## Checklist

| Area | PDF expectation | Repo status | Notes |
| --- | --- | --- | --- |
| Core backend | FastAPI service with layered backend | PASS | `app/` is layered and wired through FastAPI routers. |
| Infra stack | Postgres, pgvector, Redis, MinIO, Vault, tracing | PASS | Compose includes the stack and observability helpers are shared. |
| Auth | JWT auth with user/admin roles | PASS | Password hashing, JWTs, and token-version revocation are implemented. |
| Short-term memory | Redis-backed conversation memory | PASS | Short-term thread memory is persisted in Redis. |
| Long-term memory | Postgres memory plus audit logs | PASS | Long-term writes are redacted and audited. |
| Chat tools | Classifier, NER, summarizer, RAG, write_memory tool | PASS | The API and model server expose the required tool paths. |
| Advanced RAG | Docs + resolved issues corpus, hybrid retrieval, reranking, query rewrite | PASS | Retrieval combines sparse and dense signals with reranking. |
| Widget | Embedded React widget plus loader flow | PASS | Runtime config injection and public widget chat are implemented. |
| Streamlit admin | Internal admin console | PASS | `chatbot_streamlit/app.py` provides the operator UI. |
| Evals | Classification and RAG golden sets with thresholds | PASS | Both golden sets and evaluation scripts are present. |
| CI | Evals and safety checks in CI | PARTIAL | Local scripts and thresholds exist; repo-specific CI wiring can be extended. |
| Documentation | ARCH, DECISIONS, RUNBOOK, EVALS, SECURITY | PASS | Required docs are present and linked from the README. |
| Submission | Tag `v0.1.0-week7` | PENDING | Create the release tag once the final commit is chosen. |

## Bottom Line

The project is in demo-ready shape. The remaining work is mainly release packaging and any final polish you want before you freeze the submission.

