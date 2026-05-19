from sqlalchemy.orm import Session
from app.domain.models import Widget
import uuid

class WidgetRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, owner_id: uuid.UUID, public_id: str, allowed_origins: list = None):
        widget = Widget(
            owner_id=owner_id,
            public_id=public_id,
            allowed_origins=allowed_origins or []
        )
        self.db.add(widget)
        self.db.commit()
        self.db.refresh(widget)
        return widget

    def get_by_public_id(self, public_id: str):
        return self.db.query(Widget).filter(Widget.public_id == public_id).first()