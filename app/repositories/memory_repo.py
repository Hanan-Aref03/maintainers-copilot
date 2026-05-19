from sqlalchemy.orm import Session
from app.domain.models import LongTermMemory
import uuid

class MemoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: uuid.UUID, memory_type: str, content: str, embedding: list = None, metadata: dict = None):
        memory = LongTermMemory(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            metadata=metadata or {}
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def get_by_user(self, user_id: uuid.UUID, limit: int = 10):
        return self.db.query(LongTermMemory).filter(LongTermMemory.user_id == user_id).order_by(LongTermMemory.created_at.desc()).limit(limit).all()