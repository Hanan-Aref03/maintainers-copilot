"""Async helpers for generating memory embeddings."""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.infra.ai_clients import GeminiClient, ProviderError, VoyageClient


async def get_embedding(text: str) -> list[float] | None:
    """Return an embedding when a provider key is configured.

    Voyage is preferred for memory embeddings, with Gemini as a fallback.
    The helper returns ``None`` when no provider is available so callers can
    continue to operate in a local-only mode.
    """

    if settings.voyage_api_key:
        voyage = VoyageClient(
            api_key=settings.voyage_api_key,
            model=settings.voyage_embedding_model,
            timeout_seconds=settings.provider_timeout_seconds,
        )
        try:
            return await asyncio.to_thread(voyage.embed_text, text, "document")
        except ProviderError:
            pass

    if settings.gemini_api_key:
        gemini = GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.provider_timeout_seconds,
        )
        try:
            return await asyncio.to_thread(gemini.embed_text, text)
        except ProviderError:
            pass

    return None
