import asyncio
import json
import math
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.ai_clients import GeminiClient, ProviderError, VoyageClient
from app.repositories.memory_repo import MemoryRepository


class ChatService:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.memory_repo = MemoryRepository(db) if db is not None else None
        self.gemini = (
            GeminiClient(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                timeout_seconds=settings.provider_timeout_seconds,
            )
            if settings.gemini_api_key
            else None
        )
        self.voyage = (
            VoyageClient(
                api_key=settings.voyage_api_key,
                model=settings.voyage_embedding_model,
                timeout_seconds=settings.provider_timeout_seconds,
            )
            if settings.voyage_api_key
            else None
        )

    async def process_message(self, user_id: UUID, thread_id: str, message: str) -> str:
        cleaned_message = message.strip()
        if not cleaned_message:
            return "Please send a non-empty message."

        query_embedding = await self._maybe_embed(cleaned_message)
        memories = self._load_memories(user_id)
        relevant_memories = self._rank_memories(memories, query_embedding)
        context = self._format_memory_context(relevant_memories)
        prompt = self._build_prompt(thread_id, cleaned_message, context)

        provider = "local"
        answer = self._build_fallback_reply(cleaned_message, context)

        if self.gemini is not None:
            try:
                answer = await asyncio.to_thread(self.gemini.generate_text, prompt)
                provider = "gemini"
            except ProviderError:
                provider = "voyage-fallback" if query_embedding is not None else "local-fallback"

        self._store_memory(user_id, thread_id, cleaned_message, answer, query_embedding, provider)
        return answer

    def _load_memories(self, user_id: UUID):
        if self.memory_repo is None:
            return []
        try:
            return self.memory_repo.get_by_user(user_id, limit=25)
        except SQLAlchemyError:
            return []

    async def _maybe_embed(self, message: str) -> list[float] | None:
        if self.voyage is None:
            return None

        try:
            return await asyncio.to_thread(self.voyage.embed_text, message, "query")
        except ProviderError:
            return None

    def _rank_memories(self, memories, query_embedding: list[float] | None):
        if not memories:
            return []

        if query_embedding is None:
            return list(memories)[:3]

        scored = []
        for memory in memories:
            embedding = self._coerce_embedding(getattr(memory, "embedding", None))
            if embedding is None:
                continue
            scored.append((self._cosine_similarity(query_embedding, embedding), memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:3]] or list(memories)[:3]

    def _coerce_embedding(self, embedding) -> list[float] | None:
        if embedding is None:
            return None
        if isinstance(embedding, str):
            try:
                embedding = json.loads(embedding)
            except json.JSONDecodeError:
                return None
        if not isinstance(embedding, list):
            return None
        try:
            return [float(value) for value in embedding]
        except (TypeError, ValueError):
            return None

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
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

    def _format_memory_context(self, memories) -> str:
        if not memories:
            return "No prior memories."

        lines = []
        for memory in memories:
            content = str(getattr(memory, "content", "")).strip()
            if not content:
                continue
            lines.append(f"- {content[:700]}")

        return "\n".join(lines) if lines else "No prior memories."

    def _build_prompt(self, thread_id: str, message: str, context: str) -> str:
        return (
            "You are Maintainers Copilot, a concise assistant for open-source maintainers.\n"
            "Answer directly and practically.\n"
            "Use the retrieved memory context when it is relevant.\n"
            "If the context is empty or unrelated, answer from first principles.\n\n"
            f"Thread ID: {thread_id}\n"
            f"Relevant memory context:\n{context}\n\n"
            f"User message:\n{message}\n"
        )

    def _build_fallback_reply(self, message: str, context: str) -> str:
        if context and context != "No prior memories.":
            return (
                "Gemini is unavailable right now, so I am returning the best local memory-based fallback.\n\n"
                f"Relevant context:\n{context}\n\n"
                f"Latest message:\n{message}"
            )

        return (
            "Gemini is unavailable right now, and there is no stored context yet.\n"
            f"Latest message: {message}"
        )

    def _store_memory(
        self,
        user_id: UUID,
        thread_id: str,
        message: str,
        response: str,
        embedding: list[float] | None,
        provider: str,
    ) -> None:
        if self.memory_repo is None:
            return

        try:
            self.memory_repo.create(
                user_id=user_id,
                memory_type="episodic",
                content=f"Thread {thread_id}\nUser: {message}\nAssistant: {response}",
                embedding=embedding,
                metadata={
                    "thread_id": thread_id,
                    "provider": provider,
                },
            )
        except SQLAlchemyError:
            return
