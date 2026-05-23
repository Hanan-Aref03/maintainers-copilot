from __future__ import annotations

import hashlib
import re
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Attachment
from app.infra.blob_store import BlobStoreError, get_blob_store
from app.repositories.attachment_repo import AttachmentRepository


class AttachmentError(RuntimeError):
    pass


class AttachmentNotFoundError(AttachmentError):
    pass


class AttachmentAccessError(AttachmentError):
    pass


class AttachmentValidationError(AttachmentError):
    pass


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str | None) -> str:
    candidate = Path(filename or "attachment").name.strip()
    cleaned = _SAFE_FILENAME_RE.sub("_", candidate).strip("._")
    return cleaned or "attachment"


def _human_filename_prefix(filename: str) -> str:
    stem = Path(filename).stem or "attachment"
    return _sanitize_filename(stem)


class AttachmentService:
    def __init__(
        self,
        db: Session,
        *,
        bucket_name: str | None = None,
        blob_store=None,
        max_attachment_bytes: int | None = None,
    ) -> None:
        self.db = db
        self.repo = AttachmentRepository(db)
        self.bucket_name = bucket_name or settings.minio_bucket
        self.blob_store = blob_store or get_blob_store()
        self.max_attachment_bytes = max_attachment_bytes or settings.max_attachment_bytes

    async def upload_attachment(
        self,
        *,
        user_id: UUID,
        filename: str | None,
        content_type: str | None,
        raw_bytes: bytes,
        notes: str | None = None,
    ) -> Attachment:
        if not raw_bytes:
            raise AttachmentValidationError("Attachment is empty")
        if len(raw_bytes) > self.max_attachment_bytes:
            raise AttachmentValidationError("Attachment exceeds the maximum allowed size")

        sanitized_filename = _sanitize_filename(filename)
        object_key = (
            f"attachments/{user_id}/{uuid4().hex}/"
            f"{_human_filename_prefix(sanitized_filename)}"
        )
        checksum = hashlib.sha256(raw_bytes).hexdigest()
        normalized_notes = notes.strip() if notes and notes.strip() else None
        mime_type = content_type or "application/octet-stream"

        try:
            self.blob_store.put_object(
                object_key=object_key,
                data=raw_bytes,
                content_type=mime_type,
            )
            attachment = self.repo.create(
                owner_id=user_id,
                bucket_name=self.bucket_name,
                object_key=object_key,
                filename=sanitized_filename,
                content_type=mime_type,
                size_bytes=len(raw_bytes),
                sha256=checksum,
                notes=normalized_notes,
            )
            return attachment
        except BlobStoreError:
            raise
        except Exception as exc:
            try:
                self.blob_store.delete_object(object_key)
            except Exception:
                pass
            raise AttachmentError(str(exc)) from exc

    def list_attachments(self, user_id: UUID) -> list[Attachment]:
        return self.repo.list_by_owner(user_id)

    def get_attachment(self, user_id: UUID, attachment_id: UUID) -> Attachment:
        attachment = self.repo.get_by_id(attachment_id)
        if attachment is None:
            raise AttachmentNotFoundError("Attachment not found")
        if attachment.owner_id != user_id:
            raise AttachmentAccessError("Not allowed to access this attachment")
        return attachment

    def download_attachment(self, user_id: UUID, attachment_id: UUID) -> tuple[Attachment, bytes]:
        attachment = self.get_attachment(user_id, attachment_id)
        data = self.blob_store.get_object(attachment.object_key)
        return attachment, data
