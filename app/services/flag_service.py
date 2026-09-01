"""Feature-flag creation and environment configuration business logic."""

import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.cache import cache
from app.realtime import connection_manager
from app.models import (
    Flag,
    FlagEnvironmentConfig,
    Membership,
    Project,
    User,
)
from app.schemas import FlagCreate, FlagRuleUpdate


ENVIRONMENTS = ("development", "staging", "production")


class FlagService:
    """Handle flag mutations and their organization authorization checks."""

    @staticmethod
    def create_flag(
        db: Session, user: User, project_id: UUID, flag_data: FlagCreate
    ) -> Flag:
        """Create a flag and its default configuration rows."""

        project = db.get(Project, project_id)
        if project is None:
            raise LookupError("Project not found")
        FlagService._require_member(db, user, project.organization_id)

        key = flag_data.key.strip()
        name = flag_data.name.strip()
        if not key or not name:
            raise ValueError("Flag key and name cannot be empty")

        existing_flag = db.scalar(
            select(Flag).where(Flag.project_id == project_id, Flag.key == key)
        )
        if existing_flag is not None:
            raise ValueError("Flag key already exists in this project")

        flag = Flag(
            project_id=project_id,
            key=key,
            name=name,
            created_by=user.id,
        )
        db.add(flag)

        try:
            db.flush()
            db.add_all(
                FlagEnvironmentConfig(flag_id=flag.id, environment=environment)
                for environment in ENVIRONMENTS
            )
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Flag key already exists in this project") from exc

        db.refresh(flag)
        return flag

    @staticmethod
    def toggle_flag(
        db: Session, user: User, flag_id: UUID, environment: str, enabled: bool
    ) -> Flag:
        """Toggle a flag in one environment."""

        flag, config = FlagService._get_flag_and_config(
            db, user, flag_id, environment
        )
        config.enabled = enabled
        db.commit()
        db.refresh(flag)
        FlagService._after_config_update(flag, config)
        return flag

    @staticmethod
    def update_rollout(
        db: Session, user: User, flag_id: UUID, environment: str, percentage: int
    ) -> Flag:
        """Set the percentage rollout for one environment."""

        if not 0 <= percentage <= 100:
            raise ValueError("Rollout percentage must be between 0 and 100")

        flag, config = FlagService._get_flag_and_config(
            db, user, flag_id, environment
        )
        config.rollout_percentage = percentage
        db.commit()
        db.refresh(flag)
        FlagService._after_config_update(flag, config)
        return flag

    @staticmethod
    def update_rule(
        db: Session,
        user: User,
        flag_id: UUID,
        environment: str,
        rule: FlagRuleUpdate | None,
    ) -> Flag:
        """Set or clear the single targeting rule for one environment."""

        flag, config = FlagService._get_flag_and_config(
            db, user, flag_id, environment
        )
        if rule is None:
            config.rule_attribute = None
            config.rule_operator = None
            config.rule_value = None
        else:
            attribute = rule.attribute.strip()
            value = rule.value.strip()
            if not attribute or not value:
                raise ValueError("Rule attribute and value cannot be empty")
            config.rule_attribute = attribute
            config.rule_operator = rule.operator
            config.rule_value = value

        db.commit()
        db.refresh(flag)
        FlagService._after_config_update(flag, config)
        return flag

    @staticmethod
    def _get_flag_and_config(
        db: Session, user: User, flag_id: UUID, environment: str
    ) -> tuple[Flag, FlagEnvironmentConfig]:
        if environment not in ENVIRONMENTS:
            raise ValueError("Invalid environment")

        flag = db.scalar(
            select(Flag)
            .options(joinedload(Flag.project))
            .where(Flag.id == flag_id)
        )
        if flag is None:
            raise LookupError("Flag not found")

        FlagService._require_member(db, user, flag.project.organization_id)
        config = db.scalar(
            select(FlagEnvironmentConfig).where(
                FlagEnvironmentConfig.flag_id == flag_id,
                FlagEnvironmentConfig.environment == environment,
            )
        )
        if config is None:
            raise LookupError("Flag environment configuration not found")
        return flag, config

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
    def _after_config_update(
        flag: Flag, config: FlagEnvironmentConfig
    ) -> None:
        """Placeholder for Phase 3 cache invalidation and Phase 4 broadcast."""

        FlagService._invalidate_cache(flag.id, config.environment)
        FlagService._broadcast_update(flag, config)

    @staticmethod
    def _invalidate_cache(flag_id: UUID, environment: str) -> None:
        cache.invalidate(f"{flag_id}:{environment}")

    @staticmethod
    def _broadcast_update(flag: Flag, config: FlagEnvironmentConfig) -> None:
        if flag.project is None:
            return

        organization_id = str(flag.project.organization_id)
        message = {
            "type": "flag_updated",
            "flag_id": str(flag.id),
            "environment": config.environment,
            "enabled": config.enabled,
            "rollout_percentage": config.rollout_percentage,
        }

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                from anyio import from_thread

                from_thread.run(
                    connection_manager.broadcast, organization_id, message
                )
            except RuntimeError:
                asyncio.run(connection_manager.broadcast(organization_id, message))
        else:
            loop.create_task(connection_manager.broadcast(organization_id, message))
