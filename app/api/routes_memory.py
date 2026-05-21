from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def list_memory():
    return {"status": "ok", "items": []}
