"""Persistence operations for organization API keys."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiKey


class ApiKeyRepository:
    """Keep API-key queries and persistence separate from API-key policy."""

    @staticmethod
    def save(db: Session, api_key: ApiKey) -> ApiKey:
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        return api_key

    @staticmethod
    def list_for_organization(db: Session, organization_id: UUID) -> list[ApiKey]:
        statement = (
            select(ApiKey)
            .where(ApiKey.organization_id == organization_id)
            .order_by(ApiKey.created_at)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def get_for_organization(
        db: Session, api_key_id: UUID, organization_id: UUID
    ) -> ApiKey | None:
        return db.scalar(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.organization_id == organization_id,
            )
        )

    @staticmethod
    def get_active_by_hash(db: Session, hashed_key: str) -> ApiKey | None:
        return db.scalar(
            select(ApiKey).where(
                ApiKey.hashed_key == hashed_key,
                ApiKey.revoked_at.is_(None),
            )
        )

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
