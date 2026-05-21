from sqlalchemy.orm import Session
from app.repositories.memory_repo import MemoryRepository
from app.repositories.audit_repo import AuditRepository
from app.services.embedding_service import get_embedding
from app.domain.models import LongTermMemory
from uuid import UUID

class LongTermMemoryService:
    def __init__(self, db: Session):
        self.memory_repo = MemoryRepository(db)
        self.audit_repo = AuditRepository(db)
    
    async def store_semantic_memory(self, user_id: UUID, content: str, metadata: dict = None):
        # Generate embedding for the memory content
        embedding = await get_embedding(content)
        memory = self.memory_repo.create(
            user_id=user_id,
            memory_type="semantic",
            content=content,
            embedding=embedding,
            metadata=metadata
        )
        # Audit log
        self.audit_repo.log(
            actor_id=user_id,
            action="WRITE_MEMORY",
            target=f"memory_id:{memory.id}",
            details={"type": "semantic", "content_preview": content[:100]}
        )
        return memory
    
    def retrieve_relevant_memories(self, user_id: UUID, query: str, limit: int = 5) -> list:
        # Use pgvector similarity search (requires async, but we'll simplify with sync for now)
        # For production, you'd use cosine similarity on embedding. We'll stub.
        # Full implementation would do: order_by(LongTermMemory.embedding.cosine_distance(query_emb))
        # For now, just return recent memories.
        return self.memory_repo.get_by_user(user_id, limit=limit)
