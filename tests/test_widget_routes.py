from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_widgets
from app.api.dependencies import get_db


class FakeWidgetRepo:
    def __init__(self, db):
        self.db = db
        self.widget = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000111"),
            public_id="demo123",
            owner_id=UUID("00000000-0000-0000-0000-000000000222"),
            allowed_origins=["http://localhost:3000"],
            theme={"primary_color": "#0f766e", "position": "bottom-right"},
            greeting="Hello from the widget",
            enabled_tools=["classify", "rag", "memory"],
            created_at=None,
        )

    def get_by_public_id(self, public_id):
        if public_id == self.widget.public_id:
            return self.widget
        return None


class FakeChatService:
    def __init__(self, db=None):
        self.db = db

    async def process_message(self, user_id, thread_id, message):
        return f"echo:{thread_id}:{message}"


def test_widget_loader_injects_runtime_config_and_csp(monkeypatch, tmp_path):
    bundle = tmp_path / "widget.js"
    bundle.write_text('console.log("widget bundle");', encoding="utf-8")

    monkeypatch.setattr(routes_widgets, "WIDGET_BUNDLE_PATH", bundle)
    monkeypatch.setattr(routes_widgets, "WidgetRepository", FakeWidgetRepo)
    monkeypatch.setattr(routes_widgets, "ChatService", FakeChatService)

    app = FastAPI()
    app.include_router(routes_widgets.router, prefix="/widgets")
    app.dependency_overrides[get_db] = lambda: iter([object()])

    client = TestClient(app)

    response = client.get(
        "/widgets/widget.js",
        params={"widget_id": "demo123"},
        headers={"origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    assert "window.__COPILOT_WIDGET_CONFIG__" in response.text
    assert 'console.log("widget bundle");' in response.text
    assert response.headers["content-security-policy"] == "frame-ancestors http://localhost:3000"


def test_widget_chat_checks_origin_and_uses_public_route(monkeypatch):
    monkeypatch.setattr(routes_widgets, "WidgetRepository", FakeWidgetRepo)
    monkeypatch.setattr(routes_widgets, "ChatService", FakeChatService)

    app = FastAPI()
    app.include_router(routes_widgets.router, prefix="/widgets")
    app.dependency_overrides[get_db] = lambda: iter([object()])

    client = TestClient(app)

    ok_response = client.post(
        "/widgets/demo123/chat",
        params={"message": "hello"},
        headers={"origin": "http://localhost:3000"},
    )
    assert ok_response.status_code == 200
    assert ok_response.json()["response"] == "echo:demo123:hello"

    blocked_response = client.post(
        "/widgets/demo123/chat",
        params={"message": "hello"},
        headers={"origin": "http://evil.example"},
    )
    assert blocked_response.status_code == 403

