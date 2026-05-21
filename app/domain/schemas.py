from uuid import UUID

from pydantic import BaseModel, Field


_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class CurrentUser(BaseModel):
    id: UUID = Field(default_factory=lambda: _DEV_USER_ID)
    email: str = "dev@example.com"
    role: str = "maintainer"
