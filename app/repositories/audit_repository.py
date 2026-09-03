"""Persistence operations for flag audit-log entries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLogEntry


class AuditRepository:
    """Keep audit-log queries separate from service and router code."""

    @staticmethod
    def create(
        db: Session,
        *,
        organization_id: UUID,
        flag_id: UUID,
        actor_user_id: UUID,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLogEntry:
        """Add an audit entry to the current transaction.

        The repository deliberately does not commit. This lets the caller save
        the flag mutation and its audit entry atomically.
        """

        entry = AuditLogEntry(
            organization_id=organization_id,
            flag_id=flag_id,
            actor_user_id=actor_user_id,
            action=action,
            before=before,
            after=after,
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def list_for_flag(
        db: Session,
        *,
        organization_id: UUID,
        flag_id: UUID,
    ) -> list[AuditLogEntry]:
        """Return a flag's history, constrained to its organization."""

        statement = (
            select(AuditLogEntry)
            .where(
                AuditLogEntry.organization_id == organization_id,
                AuditLogEntry.flag_id == flag_id,
            )
            .order_by(AuditLogEntry.created_at.asc(), AuditLogEntry.id.asc())
        )
        return list(db.scalars(statement).all())
