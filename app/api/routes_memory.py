from fastapi import APIRouter, Depends, HTTPException
from app.services.memory_service import LongTermMemoryService
from app.infra.auth import current_user
from app.domain.models import User
from app.infra.database import SessionLocal

router = APIRouter()

@router.get("/")
async def get_memories(user: User = Depends(current_user)):
    db = SessionLocal()
    service = LongTermMemoryService(db)
    memories = service.retrieve_relevant_memories(user.id, "", limit=10)
    db.close()
    return [{"id": m.id, "content": m.content, "type": m.memory_type} for m in memories]