from uuid import UUID

from app.domain.schemas import CurrentUser


_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def build_dev_user() -> CurrentUser:
    return CurrentUser(id=_DEV_USER_ID)


def decode_current_user(token: str) -> CurrentUser:
    cleaned_token = token.strip()
    if not cleaned_token:
        return build_dev_user()

    try:
        return CurrentUser(id=UUID(cleaned_token))
    except (TypeError, ValueError):
        return build_dev_user()
