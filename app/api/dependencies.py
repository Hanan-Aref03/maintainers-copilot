from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.domain.schemas import CurrentUser
from app.infra.database import get_session_local
from app.infra.auth import build_dev_user, decode_current_user
from app.services.chat_service import ChatService


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    if not authorization:
        return build_dev_user()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return build_dev_user()

    return decode_current_user(token)


def get_db():
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db=db)
