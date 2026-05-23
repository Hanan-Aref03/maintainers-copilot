# Prompt Library

This folder stores prompt text separately from code so prompt changes can be reviewed, reused, and explained without digging through the implementation.

## Layout

- `issues/pandas/` - issue-style prompts based on the repo's pandas corpus
- `rag/` - prompt templates used by the retrieval and answer-generation flows

## Why this exists

- It keeps the issue prompts aligned with the dataset used for classification and RAG work.
- It gives the RAG pipeline a clear place for query rewriting, answer generation, and judge prompts.
- It makes the prompt layer easier to explain during a demo.

## Where The Code Lives

- Advanced RAG retrieval and reranking: `app/services/rag_service.py`
- End-to-end chat orchestration: `app/services/chat_service.py`
- RAG evaluation: `evals/rag_eval.py`
- RAGAS judge wiring: `evals/ragas_support.py`

