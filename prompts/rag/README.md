# RAG Prompts

This folder holds the prompt templates that support the retrieval-and-answer flow.

## Prompt Families

- `query_rewrite.md` - rewrites a user question into search-friendly issue queries
- `answer_generation.md` - builds the final maintainer response from memory and retrieved context
- `judge_faithfulness.md` - checks whether an answer stays grounded in retrieved evidence
- `judge_answer_relevancy.md` - checks whether the answer actually addresses the question

## Where These Are Used

- Retrieval and reranking live in `app/services/rag_service.py`
- Chat answer assembly lives in `app/services/chat_service.py`
- End-to-end RAG evaluation lives in `evals/rag_eval.py`
- RAGAS helper wiring lives in `evals/ragas_support.py`

