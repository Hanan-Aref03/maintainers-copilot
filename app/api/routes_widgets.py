from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from app.repositories.widget_repo import WidgetRepository
from app.infra.database import SessionLocal

router = APIRouter()

@router.get("/widget.js")
async def loader_script(request: Request, widget_id: str):
    # Fetch widget config from DB
    db = SessionLocal()
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(widget_id)
    if not widget:
        raise HTTPException(404, "Widget not found")
    # Check origin
    origin = request.headers.get("origin")
    if origin not in widget.allowed_origins:
        raise HTTPException(403, "Origin not allowed")
    # Serve the built widget script (read from file)
    with open("widget/dist/widget.js", "r") as f:
        script_content = f.read()
    # Add CSP header for frame-ancestors
    headers = {
        "Content-Security-Policy": f"frame-ancestors {' '.join(widget.allowed_origins)}",
        "Content-Type": "application/javascript"
    }
    return HTMLResponse(content=script_content, headers=headers)