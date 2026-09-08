"""Feature-flag creation and environment configuration business logic."""

import asyncio
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import cache
from app.realtime import connection_manager
from app.models import (
    Flag,
    FlagEnvironmentConfig,
    Membership,
    User,
)
from app.repositories.flag_repository import FlagRepository
from app.repositories.org_repository import OrgRepository
from app.schemas import FlagCreate, FlagRuleUpdate
from app.services.audit_service import AuditService


ENVIRONMENTS = ("development", "staging", "production")


class FlagService:
    """Handle flag mutations and their organization authorization checks."""

    @staticmethod
    def list_flags(db: Session, user: User, project_id: UUID) -> list[Flag]:
        """Return flags for a project after confirming organization membership."""

        project = FlagRepository.get_project(db, project_id)
        if project is None:
            raise LookupError("Project not found")

        FlagService._require_member(db, user, project.organization_id)
        return FlagRepository.list_for_project(db, project_id)

    @staticmethod
    def get_flag(db: Session, user: User, flag_id: UUID) -> Flag:
        """Return a flag after confirming the user belongs to its organization."""

        flag = FlagRepository.get(db, flag_id)
        if flag is None:
            raise LookupError("Flag not found")

        FlagService._require_member(db, user, flag.project.organization_id)
        return flag

    @staticmethod
    def create_flag(
        db: Session, user: User, project_id: UUID, flag_data: FlagCreate
    ) -> Flag:
        """Create a flag and its default configuration rows."""

        project = FlagRepository.get_project(db, project_id)
        if project is None:
            raise LookupError("Project not found")
        FlagService._require_member(db, user, project.organization_id)

        key = flag_data.key.strip()
        name = flag_data.name.strip()
        if not key or not name:
            raise ValueError("Flag key and name cannot be empty")

        existing_flag = FlagRepository.get_by_organization_and_key(
            db, project.organization_id, key
        )
        if existing_flag is not None:
            raise ValueError("Flag key already exists in this organization")

        flag = Flag(
            organization_id=project.organization_id,
            project_id=project_id,
            key=key,
            name=name,
            created_by=user.id,
        )
        try:
            FlagRepository.add_flag(db, flag)
            FlagRepository.flush(db)
            configs = [
                FlagEnvironmentConfig(flag_id=flag.id, environment=environment)
                for environment in ENVIRONMENTS
            ]
            FlagRepository.add_configs(db, configs)
            FlagRepository.flush(db)
            AuditService.record(
                db,
                organization_id=project.organization_id,
                flag_id=flag.id,
                actor_user_id=user.id,
                action="flag_created",
                after={
                    "flag": FlagService._flag_snapshot(flag),
                    "environments": [
                        FlagService._config_snapshot(config) for config in configs
                    ],
                },
            )
            FlagRepository.commit(db)
        except IntegrityError as exc:
            FlagRepository.rollback(db)
            raise ValueError("Flag key already exists in this organization") from exc

        FlagRepository.refresh(db, flag)
        return flag

    @staticmethod
    def toggle_flag(
        db: Session, user: User, flag_id: UUID, environment: str, enabled: bool
    ) -> Flag:
        """Toggle a flag in one environment."""

        flag, config = FlagService._get_flag_and_config(
            db, user, flag_id, environment
        )
        before = FlagService._config_snapshot(config)
        config.enabled = enabled
        AuditService.record(
            db,
            organization_id=flag.project.organization_id,
            flag_id=flag.id,
            actor_user_id=user.id,
            action="flag_toggled",
            before=before,
            after=FlagService._config_snapshot(config),
        )
        FlagRepository.commit(db)
        FlagRepository.refresh(db, flag)
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
        before = FlagService._config_snapshot(config)
        config.rollout_percentage = percentage
        AuditService.record(
            db,
            organization_id=flag.project.organization_id,
            flag_id=flag.id,
            actor_user_id=user.id,
            action="rollout_updated",
            before=before,
            after=FlagService._config_snapshot(config),
        )
        FlagRepository.commit(db)
        FlagRepository.refresh(db, flag)
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
        before = FlagService._config_snapshot(config)
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

        AuditService.record(
            db,
            organization_id=flag.project.organization_id,
            flag_id=flag.id,
            actor_user_id=user.id,
            action="rule_updated",
            before=before,
            after=FlagService._config_snapshot(config),
        )
        FlagRepository.commit(db)
        FlagRepository.refresh(db, flag)
        FlagService._after_config_update(flag, config)
        return flag

    @staticmethod
    def _get_flag_and_config(
        db: Session, user: User, flag_id: UUID, environment: str
    ) -> tuple[Flag, FlagEnvironmentConfig]:
        if environment not in ENVIRONMENTS:
            raise ValueError("Invalid environment")

        flag = FlagRepository.get(db, flag_id)
        if flag is None:
            raise LookupError("Flag not found")

        FlagService._require_member(db, user, flag.project.organization_id)
        config = FlagRepository.get_config(db, flag_id, environment)
        if config is None:
            raise LookupError("Flag environment configuration not found")
        return flag, config

    @staticmethod
    def _require_member(db: Session, user: User, organization_id: UUID) -> Membership:
        membership = OrgRepository.get_membership(db, user.id, organization_id)
        if membership is None:
            raise PermissionError("User is not a member of this organization")
        return membership

    @staticmethod
    def _flag_snapshot(flag: Flag) -> dict:
        """Return JSON-safe flag fields for audit history."""

        return {
            "id": str(flag.id),
            "project_id": str(flag.project_id),
            "key": flag.key,
            "name": flag.name,
            "on_value": flag.on_value,
            "off_value": flag.off_value,
            "created_by": str(flag.created_by),
        }

    @staticmethod
    def _config_snapshot(config: FlagEnvironmentConfig) -> dict:
        """Return JSON-safe environment settings for audit history."""

        return {
            "environment": config.environment,
            "enabled": config.enabled,
            "rollout_percentage": config.rollout_percentage,
            "rule_attribute": config.rule_attribute,
            "rule_operator": config.rule_operator,
            "rule_value": config.rule_value,
        }

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
