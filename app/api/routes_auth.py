from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.domain.models import UserRole
from app.domain.schemas import AuthToken, CurrentUser, UserLogin, UserRegister
from app.infra.auth import create_access_token, hash_password, verify_password
from app.repositories.user_repo import UserRepository


router = APIRouter()


def _to_current_user(user) -> CurrentUser:
    return CurrentUser(id=user.id, email=user.email, role=user.role.value)


def _issue_token(user) -> AuthToken:
    return AuthToken(
        access_token=create_access_token(
            user_id=user.id,
            role=user.role.value,
            token_version=int(user.token_version or 0),
        ),
        user=_to_current_user(user),
    )


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    existing = user_repo.get_by_email(payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = user_repo.create(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.MAINTAINER,
    )
    return _issue_token(user)


@router.post("/login", response_model=AuthToken)
async def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return _issue_token(user)


@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(current_user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user_repo.revoke_sessions(user)
    return {"status": "ok", "message": "Session revoked"}


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user
