from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_attachments
from app.api.dependencies import get_attachment_service, get_current_user
from app.domain.schemas import CurrentUser
from app.infra.blob_store import BlobStoreError


USER_ID = UUID("00000000-0000-0000-0000-000000000123")
ATTACHMENT_ID = UUID("00000000-0000-0000-0000-000000000456")


def _make_attachment():
    return SimpleNamespace(
        id=ATTACHMENT_ID,
        owner_id=USER_ID,
        bucket_name="copilot-attachments",
        object_key=f"attachments/{USER_ID}/demo-blob/report.txt",
        filename="report.txt",
        content_type="text/plain",
        size_bytes=14,
        sha256="a" * 64,
        notes="Demo note",
        created_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
    )


class FakeAttachmentService:
    def __init__(self, *, fail_download: bool = False):
        self.fail_download = fail_download
        self._attachment = _make_attachment()

    async def upload_attachment(self, **kwargs):
        self._attachment = SimpleNamespace(
            **{
                **self._attachment.__dict__,
                "filename": kwargs["filename"] or "attachment",
                "content_type": kwargs["content_type"] or "application/octet-stream",
                "size_bytes": len(kwargs["raw_bytes"]),
                "notes": kwargs.get("notes"),
            }
        )
        return self._attachment

    def list_attachments(self, user_id):
        return [self._attachment] if user_id == USER_ID else []

    def download_attachment(self, user_id, attachment_id):
        if self.fail_download:
            raise BlobStoreError("MinIO temporarily unavailable")
        return self._attachment, b"attachment-bytes"


def _build_client(service: FakeAttachmentService) -> TestClient:
    app = FastAPI()
    app.include_router(routes_attachments.router, prefix="/attachments")
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID,
        email="maintainer@example.com",
        role="maintainer",
    )
    app.dependency_overrides[get_attachment_service] = lambda: service
    return TestClient(app)


def test_upload_list_and_download_attachment():
    service = FakeAttachmentService()
    client = _build_client(service)

    upload_response = client.post(
        "/attachments/",
        files={"file": ("report.txt", b"hello attachment", "text/plain")},
        data={"notes": "Demo note"},
    )
    assert upload_response.status_code == 201
    upload_payload = upload_response.json()
    assert upload_payload["filename"] == "report.txt"
    assert upload_payload["notes"] == "Demo note"
    assert upload_payload["download_url"].endswith(f"/attachments/{ATTACHMENT_ID}/download")

    list_response = client.get("/attachments/")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["bucket_name"] == "copilot-attachments"
    assert list_payload[0]["download_url"].endswith(f"/attachments/{ATTACHMENT_ID}/download")

    download_response = client.get(f"/attachments/{ATTACHMENT_ID}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-disposition"] == 'attachment; filename="report.txt"'
    assert download_response.content == b"attachment-bytes"


def test_download_attachment_reports_storage_outage():
    service = FakeAttachmentService(fail_download=True)
    client = _build_client(service)

    response = client.get(f"/attachments/{ATTACHMENT_ID}/download")

    assert response.status_code == 503
    assert "MinIO temporarily unavailable" in response.text
