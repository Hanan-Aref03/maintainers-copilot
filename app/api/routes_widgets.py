from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.repositories.widget_repo import WidgetRepository

WIDGET_BUNDLE_PATH = Path(__file__).resolve().parents[2] / "widget" / "dist" / "widget.js"

router = APIRouter()

@router.get("/widget.js")
async def loader_script(
    request: Request,
    widget_id: str,
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(widget_id)
    if not widget:
        raise HTTPException(404, "Widget not found")

    origin = request.headers.get("origin")
    allowed_origins = widget.allowed_origins or []
    if origin and origin not in allowed_origins:
        raise HTTPException(403, "Origin not allowed")

    if not WIDGET_BUNDLE_PATH.exists():
        raise HTTPException(503, "Widget bundle not built")

    script_content = WIDGET_BUNDLE_PATH.read_text(encoding="utf-8")
    headers = {
        "Content-Security-Policy": f"frame-ancestors {' '.join(allowed_origins)}",
    }
    return Response(content=script_content, media_type="application/javascript", headers=headers)
