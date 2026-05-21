from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.models import Widget


class WidgetRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        owner_id: uuid.UUID,
        public_id: str,
        allowed_origins: list[str] | None = None,
        theme: dict | None = None,
        greeting: str | None = None,
        enabled_tools: list[str] | None = None,
    ) -> Widget:
        widget = Widget(
            owner_id=owner_id,
            public_id=public_id,
            allowed_origins=allowed_origins if allowed_origins is not None else [],
            theme=theme,
            greeting=greeting,
            enabled_tools=enabled_tools,
        )
        self.db.add(widget)
        self.db.commit()
        self.db.refresh(widget)
        return widget

    def get_by_public_id(self, public_id: str):
        return self.db.query(Widget).filter(Widget.public_id == public_id).first()

    def list_all(self):
        return self.db.query(Widget).order_by(Widget.created_at.desc()).all()

    def list_by_owner(self, owner_id: uuid.UUID):
        return (
            self.db.query(Widget)
            .filter(Widget.owner_id == owner_id)
            .order_by(Widget.created_at.desc())
            .all()
        )

    def update(
        self,
        widget: Widget,
        *,
        allowed_origins: list[str] | None = None,
        theme: dict | None = None,
        greeting: str | None = None,
        enabled_tools: list[str] | None = None,
    ) -> Widget:
        if allowed_origins is not None:
            widget.allowed_origins = allowed_origins
        if theme is not None:
            widget.theme = theme
        if greeting is not None:
            widget.greeting = greeting
        if enabled_tools is not None:
            widget.enabled_tools = enabled_tools

        self.db.add(widget)
        self.db.commit()
        self.db.refresh(widget)
        return widget

    def delete(self, widget: Widget) -> None:
        self.db.delete(widget)
        self.db.commit()
