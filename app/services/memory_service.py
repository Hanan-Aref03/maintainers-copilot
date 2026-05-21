from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.infra.redaction import redact_payload, redact_text
from app.infra.tracing import trace_span
from app.repositories.audit_repo import AuditRepository
from app.repositories.memory_repo import MemoryRepository

class LongTermMemoryService:
    def __init__(self, db: Session):
        self.memory_repo = MemoryRepository(db)
        self.audit_repo = AuditRepository(db)

    async def store_memory(
        self,
        user_id: UUID,
        content: str,
        memory_type: str = "semantic",
        metadata: dict | None = None,
    ):
        from app.services.embedding_service import get_embedding

        safe_content = redact_text(content)
        with trace_span(
            "memory.write",
            {
                "memory_type": memory_type,
                "content_preview": safe_content[:120],
            },
        ):
            embedding = await get_embedding(content) if memory_type != "procedural" else None
            memory = self.memory_repo.create(
                user_id=user_id,
                memory_type=memory_type,
                content=safe_content,
                embedding=embedding,
                metadata=redact_payload(metadata or {}),
            )
            self.audit_repo.log(
                actor_id=user_id,
                action="WRITE_MEMORY",
                target=f"memory_id:{memory.id}",
                details={
                    "type": memory_type,
                    "content_preview": safe_content[:100],
                },
            )
            return memory

    async def store_semantic_memory(
        self,
        user_id: UUID,
        content: str,
        metadata: dict | None = None,
    ):
        return await self.store_memory(
            user_id=user_id,
            content=content,
            memory_type="semantic",
            metadata=metadata,
        )

    def retrieve_relevant_memories(self, user_id: UUID, query: str, limit: int = 5) -> list:
        with trace_span("memory.retrieve", {"query_preview": redact_text(query)[:120], "limit": limit}):
            return self.memory_repo.get_by_user(user_id, limit=limit)
