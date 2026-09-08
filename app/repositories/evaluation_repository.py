"""Persistence operations used by flag evaluation."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FlagEnvironmentConfig


class EvaluationRepository:
    """Keep evaluation's database fallback query out of the evaluation service."""

    @staticmethod
    def get_config(
        db: Session, flag_id: UUID, environment: str
    ) -> FlagEnvironmentConfig | None:
        return db.scalar(
            select(FlagEnvironmentConfig).where(
                FlagEnvironmentConfig.flag_id == flag_id,
                FlagEnvironmentConfig.environment == environment,
            )
        )
