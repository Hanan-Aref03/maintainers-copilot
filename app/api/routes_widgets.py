from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin_user, get_current_user, get_db
from app.domain.models import UserRole
from app.domain.schemas import CurrentUser, WidgetCreate, WidgetRead, WidgetUpdate
from app.services.chat_service import ChatService
from app.repositories.widget_repo import WidgetRepository
from shared.observability import trace_span

WIDGET_BUNDLE_PATH = Path(__file__).resolve().parents[2] / "widget" / "dist" / "widget.js"

router = APIRouter()


def _normalize_origins(origins: list[str] | None) -> list[str]:
    if not origins:
        return []

    cleaned: list[str] = []
    for origin in origins:
        value = origin.strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def _widget_to_read(widget) -> WidgetRead:
    return WidgetRead(
        id=widget.id,
        public_id=widget.public_id,
        owner_id=widget.owner_id,
        allowed_origins=list(widget.allowed_origins or []),
        theme=dict(widget.theme or {"primary_color": "#3b82f6", "position": "bottom-right"}),
        greeting=widget.greeting or "Hi! How can I help with issue triage?",
        enabled_tools=list(widget.enabled_tools or []),
        created_at=widget.created_at,
    )


@router.get("/widget.js")
async def loader_script(
    request: Request,
    widget_id: str,
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(widget_id)
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    origin = request.headers.get("origin")
    allowed_origins = widget.allowed_origins or []
    if origin and origin not in allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")

    if not WIDGET_BUNDLE_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Widget bundle not built",
        )

    runtime_config = {
        "apiUrl": f"{request.url.scheme}://{request.url.netloc}",
        "widgetId": widget.public_id,
        "theme": dict(widget.theme or {"primary_color": "#3b82f6", "position": "bottom-right"}),
        "greeting": widget.greeting or "Hi! How can I help with issue triage?",
        "enabledTools": list(widget.enabled_tools or []),
        "allowedOrigins": allowed_origins,
    }
    script_content = "window.__COPILOT_WIDGET_CONFIG__ = " + json.dumps(runtime_config) + ";\n"
    script_content += WIDGET_BUNDLE_PATH.read_text(encoding="utf-8")
    headers = {}
    if allowed_origins:
        headers["Content-Security-Policy"] = f"frame-ancestors {' '.join(allowed_origins)}"
    return Response(content=script_content, media_type="application/javascript", headers=headers)


@router.post("/{public_id}/chat")
async def widget_chat(
    public_id: str,
    request: Request,
    message: str,
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(public_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    origin = request.headers.get("origin")
    allowed_origins = widget.allowed_origins or []
    if origin and origin not in allowed_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")

    if widget.owner_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Widget owner missing")

    with trace_span(
        "widget.chat",
        {
            "widget_id": public_id,
            "origin": origin or "unknown",
            "message_preview": message[:200],
        },
    ):
        service = ChatService(db=db)
        if hasattr(service, "process_message_with_metadata"):
            response = await service.process_message_with_metadata(
                user_id=widget.owner_id,
                thread_id=public_id,
                message=message,
            )
            if isinstance(response, dict) and "response" in response:
                return response

        response_text = await service.process_message(
            user_id=widget.owner_id,
            thread_id=public_id,
            message=message,
        )
        return {"response": response_text}


@router.get("/", response_model=list[WidgetRead])
async def list_widgets(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widgets = repo.list_all() if current_user.role == UserRole.ADMIN.value else repo.list_by_owner(current_user.id)
    return [_widget_to_read(widget) for widget in widgets]


@router.post("/", response_model=WidgetRead, status_code=status.HTTP_201_CREATED)
async def create_widget(
    payload: WidgetCreate,
    current_user: CurrentUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    public_id = (payload.public_id or uuid4().hex[:12]).strip()
    if repo.get_by_public_id(public_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Widget already exists")

    widget = repo.create(
        owner_id=current_user.id,
        public_id=public_id,
        allowed_origins=_normalize_origins(payload.allowed_origins),
        theme=payload.theme,
        greeting=payload.greeting,
        enabled_tools=payload.enabled_tools,
    )
    return _widget_to_read(widget)


@router.get("/{public_id}", response_model=WidgetRead)
async def get_widget(
    public_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(public_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    if current_user.role != UserRole.ADMIN.value and widget.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this widget")

    return _widget_to_read(widget)


@router.patch("/{public_id}", response_model=WidgetRead)
async def update_widget(
    public_id: str,
    payload: WidgetUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(public_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    if current_user.role != UserRole.ADMIN.value and widget.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update this widget")

    widget = repo.update(
        widget,
        allowed_origins=_normalize_origins(payload.allowed_origins) if payload.allowed_origins is not None else None,
        theme=payload.theme,
        greeting=payload.greeting,
        enabled_tools=payload.enabled_tools,
    )
    return _widget_to_read(widget)


@router.delete("/{public_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    public_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = WidgetRepository(db)
    widget = repo.get_by_public_id(public_id)
    if widget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    if current_user.role != UserRole.ADMIN.value and widget.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this widget")

    repo.delete(widget)
