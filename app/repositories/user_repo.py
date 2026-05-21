from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import User, UserRole


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: UUID | str):
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str):
        normalized_email = email.strip().lower()
        return self.db.query(User).filter(User.email == normalized_email).first()

    def list_all(self):
        return self.db.query(User).order_by(User.created_at.desc()).all()

    def create(
        self,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.MAINTAINER,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            role=role,
            token_version=0,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_role(self, user: User, role: UserRole) -> User:
        user.role = role
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def revoke_sessions(self, user: User) -> User:
        user.token_version = int(user.token_version or 0) + 1
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
