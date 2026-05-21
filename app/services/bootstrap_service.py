from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import UserRole
from app.infra.auth import hash_password
from app.infra.tracing import trace_span
from app.repositories.user_repo import UserRepository
from app.repositories.widget_repo import WidgetRepository

logger = logging.getLogger(__name__)


def bootstrap_demo_data(db: Session) -> dict[str, bool]:
    """Create the demo admin and widget if they do not already exist."""

    user_repo = UserRepository(db)
    widget_repo = WidgetRepository(db)
    created_admin = False
    created_widget = False

    with trace_span(
        "bootstrap.demo_data",
        {
            "admin_email": settings.bootstrap_admin_email,
            "widget_id": settings.demo_widget_public_id,
        },
    ):
        admin = user_repo.get_by_email(settings.bootstrap_admin_email)
        if admin is None:
            admin = user_repo.create(
                email=settings.bootstrap_admin_email,
                hashed_password=hash_password(settings.bootstrap_admin_password),
                role=UserRole.ADMIN,
            )
            created_admin = True
        elif admin.role != UserRole.ADMIN:
            user_repo.set_role(admin, UserRole.ADMIN)

        widget = widget_repo.get_by_public_id(settings.demo_widget_public_id)
        allowed_origins = [
            origin.strip()
            for origin in settings.demo_widget_allowed_origins.split(",")
            if origin.strip()
        ]
        if widget is None:
            widget_repo.create(
                owner_id=admin.id,
                public_id=settings.demo_widget_public_id,
                allowed_origins=allowed_origins,
                theme={"primary_color": "#0f766e", "position": "bottom-right"},
                greeting=settings.demo_widget_greeting,
                enabled_tools=["classify", "rag", "memory"],
            )
            created_widget = True
        else:
            widget_repo.update(
                widget,
                allowed_origins=allowed_origins,
                theme=widget.theme
                or {"primary_color": "#0f766e", "position": "bottom-right"},
                greeting=settings.demo_widget_greeting,
                enabled_tools=widget.enabled_tools or ["classify", "rag", "memory"],
            )

    logger.info(
        "Demo bootstrap complete (admin_created=%s, widget_created=%s)",
        created_admin,
        created_widget,
    )
    return {"admin_created": created_admin, "widget_created": created_widget}
