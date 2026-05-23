from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status

from app.api.dependencies import get_attachment_service, get_current_user
from app.domain.schemas import AttachmentRead, CurrentUser
from app.infra.blob_store import BlobStoreError
from app.services.attachment_service import (
    AttachmentAccessError,
    AttachmentError,
    AttachmentNotFoundError,
    AttachmentService,
    AttachmentValidationError,
)

router = APIRouter()


def _attachment_to_read(attachment, request: Request) -> AttachmentRead:
    return AttachmentRead(
        id=attachment.id,
        owner_id=attachment.owner_id,
        bucket_name=attachment.bucket_name,
        object_key=attachment.object_key,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        sha256=attachment.sha256,
        notes=attachment.notes,
        created_at=attachment.created_at,
        download_url=str(request.url_for("download_attachment", attachment_id=str(attachment.id))),
    )


@router.get("/", response_model=list[AttachmentRead])
async def list_attachments(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    attachments = attachment_service.list_attachments(current_user.id)
    return [_attachment_to_read(attachment, request) for attachment in attachments]


@router.post("/", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    try:
        raw_bytes = await file.read()
        attachment = await attachment_service.upload_attachment(
            user_id=current_user.id,
            filename=file.filename,
            content_type=file.content_type,
            raw_bytes=raw_bytes,
            notes=notes,
        )
    except AttachmentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except BlobStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AttachmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return _attachment_to_read(attachment, request)


@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    attachment_service: AttachmentService = Depends(get_attachment_service),
):
    try:
        attachment, data = attachment_service.download_attachment(current_user.id, attachment_id)
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AttachmentAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BlobStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AttachmentError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    filename = attachment.filename.replace('"', "")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(
        content=data,
        media_type=attachment.content_type or "application/octet-stream",
        headers=headers,
    )
