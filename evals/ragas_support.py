from __future__ import annotations

import asyncio
import json
import math
from typing import Iterable

from ragas.embeddings.base import BaseRagasEmbedding
from ragas.llms.base import InstructorBaseRagasLLM, InstructorTypeVar
from ragas.metrics.collections.answer_relevancy.metric import AnswerRelevancy
from ragas.metrics.collections.faithfulness.metric import Faithfulness

from app.core.config import settings
from app.infra.ai_clients import GeminiClient

GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
GEMINI_EMBEDDING_DIMENSION = 1536


def _mean_without_nan(values: Iterable[float]) -> float:
    cleaned = [value for value in values if not math.isnan(value)]
    if not cleaned:
        return 0.0
    return float(sum(cleaned) / len(cleaned))


def _safe_json_loads(text: str):
    cleaned = text.strip()
    if not cleaned:
        return None

    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()

    candidates = [cleaned]
    if "[" in cleaned and "]" in cleaned:
        candidates.append(cleaned[cleaned.find("[") : cleaned.rfind("]") + 1])
    if "{" in cleaned and "}" in cleaned:
        candidates.append(cleaned[cleaned.find("{") : cleaned.rfind("}") + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


class GeminiInstructorRagasLLM(InstructorBaseRagasLLM):
    def __init__(self, client: GeminiClient, model_name: str):
        self.client = client
        self.model_name = model_name

    def _generate(self, prompt: str, response_model: type[InstructorTypeVar]) -> InstructorTypeVar:
        prompt_text = f"{prompt}\n\nReturn only valid JSON for the requested schema."
        raw = self.client.generate_text(prompt_text)
        try:
            return response_model.model_validate_json(raw)
        except Exception:
            payload = _safe_json_loads(raw)
            if payload is not None:
                return response_model.model_validate(payload)
            raise

    def generate(self, prompt: str, response_model: type[InstructorTypeVar]) -> InstructorTypeVar:
        return self._generate(prompt, response_model)

    async def agenerate(
        self,
        prompt: str,
        response_model: type[InstructorTypeVar],
    ) -> InstructorTypeVar:
        return await asyncio.to_thread(self._generate, prompt, response_model)


def build_ragas_llm(model_name: str | None = None) -> GeminiInstructorRagasLLM:
    resolved_model = model_name or settings.gemini_model
    client = GeminiClient(
        api_key=settings.gemini_api_key,
        model=resolved_model,
        timeout_seconds=settings.provider_timeout_seconds,
    )
    return GeminiInstructorRagasLLM(client, resolved_model)


class GeminiRagasEmbeddings(BaseRagasEmbedding):
    def __init__(
        self,
        client: GeminiClient,
        model_name: str = GEMINI_EMBEDDING_MODEL,
        output_dimensionality: int = GEMINI_EMBEDDING_DIMENSION,
    ) -> None:
        super().__init__()
        self._client = client
        self._model_name = model_name
        self._output_dimensionality = output_dimensionality

    def _embed(self, text: str) -> list[float]:
        return self._client.embed_text(
            text,
            model=self._model_name,
            output_dimensionality=self._output_dimensionality,
        )

    def embed_text(self, text: str, **kwargs) -> list[float]:
        del kwargs
        return self._embed(text)

    async def aembed_text(self, text: str, **kwargs) -> list[float]:
        del kwargs
        return await asyncio.to_thread(self._embed, text)

    def embed_texts(self, texts: list[str], **kwargs) -> list[list[float]]:
        del kwargs
        return [self._embed(text) for text in texts]


def build_ragas_metrics(
    llm: InstructorBaseRagasLLM,
    embeddings: BaseRagasEmbedding,
    strictness: int = 2,
):
    return [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=embeddings, strictness=strictness),
    ]


def mean_ragas_scores(result, metric_names: list[str]) -> dict[str, float]:
    return {metric_name: _mean_without_nan(result[metric_name]) for metric_name in metric_names}
