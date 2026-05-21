from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CurrentUser(BaseModel):
    id: UUID
    email: str = Field(pattern=_EMAIL_PATTERN)
    role: str = Field(default="maintainer", pattern="^(admin|maintainer)$")


class UserRegister(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=12, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=128)


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: CurrentUser


class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=1)
    memory_type: str = Field(default="semantic", pattern="^(episodic|semantic|procedural)$")
    metadata: dict[str, Any] = Field(default_factory=dict)


class WidgetCreate(BaseModel):
    public_id: str | None = Field(default=None, min_length=3, max_length=128)
    allowed_origins: list[str] = Field(default_factory=list)
    theme: dict[str, Any] = Field(
        default_factory=lambda: {"primary_color": "#3b82f6", "position": "bottom-right"}
    )
    greeting: str = "Hi! How can I help with issue triage?"
    enabled_tools: list[str] = Field(default_factory=lambda: ["classify", "rag", "memory"])


class WidgetUpdate(BaseModel):
    allowed_origins: list[str] | None = None
    theme: dict[str, Any] | None = None
    greeting: str | None = None
    enabled_tools: list[str] | None = None


class WidgetRead(BaseModel):
    id: UUID
    public_id: str
    owner_id: UUID | None = None
    allowed_origins: list[str] = Field(default_factory=list)
    theme: dict[str, Any] = Field(
        default_factory=lambda: {"primary_color": "#3b82f6", "position": "bottom-right"}
    )
    greeting: str
    enabled_tools: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
