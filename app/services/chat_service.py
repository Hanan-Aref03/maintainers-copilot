import asyncio
import json
import math
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.ai_clients import GeminiClient, ProviderError, VoyageClient
from app.services.conversation_snapshot_service import ConversationSnapshotService
from app.infra.redaction import redact_text
from app.infra.tracing import trace_span
from app.infra.redis_client import ShortTermMemory
from app.repositories.memory_repo import MemoryRepository
from app.services.rag_service import retrieve_context


class ChatService:
    def __init__(self, db: Session | None = None, *, snapshot_service: ConversationSnapshotService | None = None) -> None:
        self.db = db
        self.memory_repo = MemoryRepository(db) if db is not None else None
        self.snapshot_service = snapshot_service or ConversationSnapshotService()
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
        result = await self.process_message_with_metadata(user_id, thread_id, message)
        return str(result["response"])

    async def process_message_with_metadata(
        self,
        user_id: UUID,
        thread_id: str,
        message: str,
    ) -> dict[str, object]:
        cleaned_message = message.strip()
        if not cleaned_message:
            return {
                "response": "Please send a non-empty message.",
                "used_fallback": True,
                "llm_provider": "local",
                "fallback_reason": "empty_message",
                "retrieved_doc_ids": [],
                "retrieved_contexts": [],
                "memory_count": 0,
                "conversation_count": 0,
            }

        with trace_span(
            "chat.process_message",
            {
                "thread_id": thread_id,
                "message_preview": redact_text(cleaned_message)[:200],
                "user_id": str(user_id),
            },
        ):
            query_embedding = await self._maybe_embed(cleaned_message)
            short_term_messages = await self._load_short_term_messages(thread_id)
            memories = self._load_memories(user_id)
            retrieved_docs = await self._load_rag_context(cleaned_message)
            relevant_memories = self._rank_memories(memories, query_embedding)
            memory_context = self._format_memory_context(relevant_memories)
            rag_context = self._format_rag_context(retrieved_docs)
            conversation_context = self._format_short_term_context(short_term_messages)
            prompt = self._build_prompt(
                thread_id,
                cleaned_message,
                memory_context,
                rag_context,
                conversation_context,
            )

            answer = self._build_fallback_reply(cleaned_message, memory_context, rag_context)
            used_fallback = True
            llm_provider = "local"
            fallback_reason = "provider_missing"

            if self.gemini is not None:
                try:
                    with trace_span(
                        "llm.generate",
                        {
                            "provider": "gemini",
                            "model": settings.gemini_model,
                            "prompt_preview": redact_text(prompt)[:500],
                        },
                    ):
                        answer = await asyncio.to_thread(self.gemini.generate_text, prompt)
                        used_fallback = False
                        llm_provider = "gemini"
                        fallback_reason = None
                except ProviderError:
                    answer = self._build_fallback_reply(cleaned_message, memory_context, rag_context)
                    used_fallback = True
                    llm_provider = "local"
                    fallback_reason = "provider_error"

            safe_answer = redact_text(answer)
            await self._append_short_term_message(thread_id, "user", cleaned_message)
            await self._append_short_term_message(thread_id, "assistant", safe_answer)
            result = {
                "response": safe_answer,
                "used_fallback": used_fallback,
                "llm_provider": llm_provider,
                "fallback_reason": fallback_reason,
                "retrieved_doc_ids": [doc.get("id") for doc in retrieved_docs],
                "retrieved_contexts": [
                    f"{str(doc.get('title') or '').strip()}\n{str(doc.get('body') or '').strip()}".strip()
                    for doc in retrieved_docs
                ],
                "memory_count": len(relevant_memories),
                "conversation_count": len(short_term_messages),
            }
            await self._record_conversation_snapshot(
                thread_id=thread_id,
                user_id=user_id,
                message=cleaned_message,
                result=result,
                retrieved_docs=retrieved_docs,
            )
            return result

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
            with trace_span(
                "embedding.query",
                {
                    "provider": "voyage",
                    "model": settings.voyage_embedding_model,
                    "input_preview": redact_text(message)[:240],
                },
            ):
                return await asyncio.to_thread(self.voyage.embed_text, message, "query")
        except ProviderError:
            return None

    async def _load_short_term_messages(self, thread_id: str):
        try:
            return await ShortTermMemory.load_conversation(thread_id)
        except Exception:
            return []

    async def _append_short_term_message(self, thread_id: str, role: str, content: str) -> None:
        try:
            await ShortTermMemory.append_message(
                thread_id,
                role,
                content,
                ttl_seconds=settings.short_term_memory_ttl_seconds,
            )
        except Exception:
            return

    async def _record_conversation_snapshot(
        self,
        *,
        thread_id: str,
        user_id: UUID,
        message: str,
        result: dict[str, object],
        retrieved_docs,
    ) -> None:
        try:
            await asyncio.to_thread(
                self.snapshot_service.record_snapshot,
                thread_id=thread_id,
                payload={
                    "user_id": str(user_id),
                    "thread_id": thread_id,
                    "message": message,
                    "response": str(result.get("response") or ""),
                    "llm_provider": result.get("llm_provider"),
                    "used_fallback": bool(result.get("used_fallback", False)),
                    "fallback_reason": result.get("fallback_reason"),
                    "retrieved_doc_ids": [doc.get("id") for doc in retrieved_docs],
                    "retrieved_contexts": [
                        f"{str(doc.get('title') or '').strip()}\n{str(doc.get('body') or '').strip()}".strip()
                        for doc in retrieved_docs
                    ],
                    "memory_count": result.get("memory_count", 0),
                    "conversation_count": result.get("conversation_count", 0),
                },
            )
        except Exception:
            return

    async def _load_rag_context(self, message: str):
        try:
            return await retrieve_context(message, top_k=3)
        except Exception:
            return []

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
            lines.append(f"- {redact_text(content)[:700]}")

        return "\n".join(lines) if lines else "No prior memories."

    def _format_rag_context(self, docs) -> str:
        if not docs:
            return "No retrieved issue context."

        lines = []
        for doc in docs:
            title = redact_text(str(doc.get("title") or "")).strip()
            body = redact_text(str(doc.get("body") or "")).strip()
            if title:
                lines.append(f"- {title}")
            if body:
                lines.append(f"  {body[:400]}")
        return "\n".join(lines) if lines else "No retrieved issue context."

    def _format_short_term_context(self, messages) -> str:
        if not messages:
            return "No recent conversation."

        lines = []
        for message in messages[-8:]:
            role = str(message.get("role") or "user").strip()
            content = str(message.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {content[:500]}")

        return "\n".join(lines) if lines else "No recent conversation."

    def _build_prompt(
        self,
        thread_id: str,
        message: str,
        memory_context: str,
        rag_context: str,
        conversation_context: str,
    ) -> str:
        return (
            "You are Maintainers Copilot, a concise assistant for open-source maintainers.\n"
            "Answer directly and practically.\n"
            "Use the retrieved memory and issue context when it is relevant.\n"
            "Use the recent conversation context when it is relevant.\n"
            "If the context is empty or unrelated, answer from first principles.\n\n"
            f"Thread ID: {thread_id}\n"
            f"Relevant memory context:\n{memory_context}\n\n"
            f"Retrieved issue context:\n{rag_context}\n\n"
            f"Recent conversation context:\n{conversation_context}\n\n"
            f"User message:\n{message}\n"
        )

    def _build_fallback_reply(self, message: str, memory_context: str, rag_context: str) -> str:
        if (memory_context and memory_context != "No prior memories.") or (
            rag_context and rag_context != "No retrieved issue context."
        ):
            return (
                "Gemini is unavailable right now, so I am returning the best local memory-based fallback.\n\n"
                f"Relevant memory context:\n{memory_context}\n\n"
                f"Retrieved issue context:\n{rag_context}\n\n"
                f"Latest message:\n{message}"
            )

        return (
            "Gemini is unavailable right now, and there is no stored context yet.\n"
            f"Latest message: {message}"
        )
