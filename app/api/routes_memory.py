from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.domain.schemas import CurrentUser, MemoryWriteRequest
from app.services.memory_service import LongTermMemoryService

router = APIRouter()

@router.get("/")
async def get_memories(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LongTermMemoryService(db)
    memories = service.retrieve_relevant_memories(current_user.id, "", limit=10)
    return [{"id": m.id, "content": m.content, "type": m.memory_type} for m in memories]


@router.post("/write")
async def write_memory(
    payload: MemoryWriteRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LongTermMemoryService(db)
    memory = await service.store_memory(
        user_id=current_user.id,
        content=payload.content,
        memory_type=payload.memory_type,
        metadata=payload.metadata,
    )
    return {
        "id": memory.id,
        "content": memory.content,
        "type": memory.memory_type,
    }
