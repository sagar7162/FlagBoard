"""Persistence operations for flags and environment configurations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Flag, FlagEnvironmentConfig, Project


class FlagRepository:
    """Keep flag queries and persistence separate from flag business rules."""

    @staticmethod
    def get_project(db: Session, project_id: UUID) -> Project | None:
        return db.get(Project, project_id)

    @staticmethod
    def list_for_project(db: Session, project_id: UUID) -> list[Flag]:
        statement = (
            select(Flag)
            .options(selectinload(Flag.environment_configs))
            .where(Flag.project_id == project_id)
            .order_by(Flag.key)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def get(db: Session, flag_id: UUID) -> Flag | None:
        return db.scalar(
            select(Flag)
            .options(joinedload(Flag.project))
            .where(Flag.id == flag_id)
        )

    @staticmethod
    def get_by_organization_and_key(
        db: Session, organization_id: UUID, key: str
    ) -> Flag | None:
        return db.scalars(
            select(Flag)
            .options(joinedload(Flag.project))
            .where(
                Flag.organization_id == organization_id,
                Flag.key == key,
            )
        ).first()

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

    @staticmethod
    def add_flag(db: Session, flag: Flag) -> None:
        db.add(flag)

    @staticmethod
    def add_configs(db: Session, configs: list[FlagEnvironmentConfig]) -> None:
        db.add_all(configs)

    @staticmethod
    def flush(db: Session) -> None:
        db.flush()

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()

    @staticmethod
    def refresh(db: Session, flag: Flag) -> None:
        db.refresh(flag)

    @staticmethod
    def rollback(db: Session) -> None:
        db.rollback()
