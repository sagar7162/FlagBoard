"""Persistence operations for users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    """Keep user queries and persistence separate from authentication logic."""

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    @staticmethod
    def get_by_id(db: Session, user_id: UUID) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def create(db: Session, user: User) -> User:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def rollback(db: Session) -> None:
        db.rollback()
