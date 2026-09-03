"""Business logic for recording and reading flag audit history."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLogEntry
from app.repositories.audit_repository import AuditRepository


AUDIT_ACTIONS = frozenset(
    {
        "flag_created",
        "flag_toggled",
        "rollout_updated",
        "rule_updated",
    }
)


class AuditService:
    """Coordinate audit persistence without owning database query details."""

    @staticmethod
    def record(
        db: Session,
        *,
        organization_id: UUID,
        flag_id: UUID,
        actor_user_id: UUID,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLogEntry:
        """Record a flag mutation in the caller's current transaction."""

        if action not in AUDIT_ACTIONS:
            raise ValueError(f"Unsupported audit action: {action}")

        return AuditRepository.create(
            db,
            organization_id=organization_id,
            flag_id=flag_id,
            actor_user_id=actor_user_id,
            action=action,
            before=before,
            after=after,
        )

    @staticmethod
    def list_for_flag(
        db: Session,
        *,
        organization_id: UUID,
        flag_id: UUID,
    ) -> list[AuditLogEntry]:
        """Return audit entries for a flag within the requesting organization."""

        return AuditRepository.list_for_flag(
            db,
            organization_id=organization_id,
            flag_id=flag_id,
        )
