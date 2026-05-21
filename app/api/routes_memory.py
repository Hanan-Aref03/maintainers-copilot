from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.services.memory_service import LongTermMemoryService
from app.domain.schemas import CurrentUser

router = APIRouter()

@router.get("/")
async def get_memories(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = LongTermMemoryService(db)
    memories = service.retrieve_relevant_memories(current_user.id, "", limit=10)
    return [{"id": m.id, "content": m.content, "type": m.memory_type} for m in memories]
