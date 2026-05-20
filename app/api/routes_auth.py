from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.domain.schemas import CurrentUser


router = APIRouter()


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user.model_dump()
