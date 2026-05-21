import json
import math
from functools import lru_cache
from typing import Any, Dict, List

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.infra.ai_clients import GeminiClient, ProviderError

# Load knowledge base once at module load.
with open("data_pipeline/knowledge_base.json", encoding="utf-8") as f:
    KNOWLEDGE_BASE = json.load(f)

# Pre-process documents for BM25: tokenize.
doc_texts = [f"{doc['title']}\n{doc['body']}" for doc in KNOWLEDGE_BASE]
tokenized_docs = [text.lower().split() for text in doc_texts]
bm25 = BM25Okapi(tokenized_docs)

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSION = 1536

_embedding_cache: dict[str, list[float]] = {}

gemini = (
    GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.provider_timeout_seconds,
    )
    if settings.gemini_api_key
    else None
)


@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


def _prepare_query_embedding_text(query: str) -> str:
    return f"task: question answering | query: {query}"


def _prepare_document_embedding_text(doc: Dict[str, Any]) -> str:
    title = str(doc.get("title") or "none").strip() or "none"
    body = str(doc.get("body") or "").strip()
    return f"title: {title} | text: {body}"


def _normalize_scores(scores: List[float]) -> np.ndarray:
    values = np.asarray(scores, dtype=float)
    if values.size == 0:
        return values

    minimum = np.min(values)
    maximum = np.max(values)
    if np.isclose(maximum, minimum):
        return np.zeros_like(values)

    return (values - minimum) / (maximum - minimum)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0

    length = min(len(left), len(right))
    if length == 0:
        return 0.0

    left = left[:length]
    right = right[:length]

    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    denominator = left_norm * right_norm
    if denominator == 0:
        return 0.0
    return numerator / denominator


def get_embedding(text: str) -> List[float] | None:
    if text in _embedding_cache:
        return _embedding_cache[text]
    if gemini is None:
        return None

    try:
        embedding = gemini.embed_text(
            text,
            model=EMBEDDING_MODEL,
            output_dimensionality=EMBEDDING_DIMENSION,
        )
    except ProviderError:
        return None

    _embedding_cache[text] = embedding
    return embedding


def hybrid_retrieve(query: str, top_k: int = 10, alpha: float = 0.5):
    # 1. Sparse (BM25)
    query_tokens = query.lower().split()
    bm25_scores = bm25.get_scores(query_tokens)
    bm25_norm = _normalize_scores(bm25_scores)

    # 2. Dense (cosine similarity)
    query_emb = get_embedding(_prepare_query_embedding_text(query))
    if query_emb is None:
        hybrid_scores = bm25_norm
    else:
        dense_scores: list[float] = []
        for doc in KNOWLEDGE_BASE:
            doc_emb = get_embedding(_prepare_document_embedding_text(doc))
            if doc_emb is None:
                dense_scores.append(0.0)
                continue
            dense_scores.append(_cosine_similarity(query_emb, doc_emb))

        dense_norm = _normalize_scores(dense_scores)
        hybrid_scores = alpha * dense_norm + (1 - alpha) * bm25_norm

    top_indices = np.argsort(hybrid_scores)[-top_k:][::-1]
    return [(KNOWLEDGE_BASE[i], float(hybrid_scores[i])) for i in top_indices]


def rerank(query: str, candidates: List[tuple]) -> List[tuple]:
    if not candidates:
        return []

    try:
        reranker = _get_reranker()
    except Exception:
        return candidates

    pairs = [(query, candidate[0]["title"] + "\n" + candidate[0]["body"]) for candidate in candidates]
    try:
        scores = reranker.predict(pairs)
    except Exception:
        return candidates

    scored = [(candidates[i][0], scores[i]) for i in range(len(candidates))]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def query_transform(original_question: str) -> str:
    if gemini is None:
        return original_question

    prompt = f"""Rewrite the following user question into 2-3 search queries that would help find relevant GitHub issues.
Original: {original_question}
Return only the search queries, one per line."""

    try:
        response = gemini.generate_text(prompt)
    except ProviderError:
        return original_question

    queries = [line.strip(" -*\t") for line in response.splitlines() if line.strip()]
    combined = " ".join(query for query in queries if query)
    return combined or original_question


async def retrieve_context(question: str, top_k: int = 5) -> List[Dict]:
    # 1. Query transformation
    transformed = query_transform(question)

    # 2. Hybrid retrieval (use transformed query)
    initial = hybrid_retrieve(transformed, top_k=10, alpha=0.6)

    # 3. Rerank
    reranked = rerank(transformed, initial)

    # Return top_k after reranking
    return [doc for doc, score in reranked[:top_k]]
