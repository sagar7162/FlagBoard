"""API-key creation, listing, and revocation."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import hash_api_key
from app.models import ApiKey, Membership, User


class ApiKeyService:
    """Handle organization-scoped evaluation keys and their authorization."""

    @staticmethod
    def create(
        db: Session, actor: User, organization_id: UUID, environment: str
    ) -> tuple[ApiKey, str]:
        """Create an API key and return its database record plus raw secret."""

        ApiKeyService._require_owner(db, actor, organization_id)
        raw_key = f"ffb_{secrets.token_urlsafe(32)}"
        api_key = ApiKey(
            organization_id=organization_id,
            environment=environment,
            hashed_key=hash_api_key(raw_key),
            key_prefix=raw_key[:12],
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        return api_key, raw_key

    @staticmethod
    def list_for_organization(
        db: Session, actor: User, organization_id: UUID
    ) -> list[ApiKey]:
        """List API-key metadata for any organization member."""

        ApiKeyService._require_member(db, actor, organization_id)
        return list(
            db.scalars(
                select(ApiKey)
                .where(ApiKey.organization_id == organization_id)
                .order_by(ApiKey.created_at)
            ).all()
        )

    @staticmethod
    def revoke(
        db: Session, actor: User, organization_id: UUID, api_key_id: UUID
    ) -> None:
        """Revoke an API key without deleting its database record."""

        ApiKeyService._require_owner(db, actor, organization_id)
        api_key = db.scalar(
            select(ApiKey).where(
                ApiKey.id == api_key_id,
                ApiKey.organization_id == organization_id,
            )
        )
        if api_key is None:
            raise LookupError("API key not found")

        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def _require_member(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == organization_id,
            )
        )
        if membership is None:
            raise PermissionError("User is not a member of this organization")
        return membership

    @staticmethod
    def _require_owner(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = ApiKeyService._require_member(db, user, organization_id)
        if membership.role != "owner":
            raise PermissionError("Only organization owners can manage API keys")
        return membership
