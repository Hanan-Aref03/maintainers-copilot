from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def list_widgets():
    return {"status": "ok", "items": []}
