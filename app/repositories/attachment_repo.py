from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Attachment


class AttachmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        owner_id: UUID,
        bucket_name: str,
        object_key: str,
        filename: str,
        size_bytes: int,
        sha256: str,
        content_type: str | None = None,
        notes: str | None = None,
        attachment_id: UUID | None = None,
    ) -> Attachment:
        attachment = Attachment(
            id=attachment_id or uuid.uuid4(),
            owner_id=owner_id,
            bucket_name=bucket_name,
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=sha256,
            notes=notes,
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def get_by_id(self, attachment_id: UUID) -> Attachment | None:
        return self.db.query(Attachment).filter(Attachment.id == attachment_id).first()

    def list_by_owner(self, owner_id: UUID) -> list[Attachment]:
        return (
            self.db.query(Attachment)
            .filter(Attachment.owner_id == owner_id)
            .order_by(Attachment.created_at.desc())
            .all()
        )
