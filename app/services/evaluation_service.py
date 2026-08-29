"""Database-backed flag evaluation orchestration."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.engine.evaluator import (
    EvalUser,
    EvaluationEngine,
    FlagConfig,
    TargetingRule,
)
from app.models import ApiKey, Flag, FlagEnvironmentConfig, Project
from app.schemas import EvaluationResponse, EvaluationUser


class EvaluationService:
    """Resolve organization-scoped flags using the pure evaluation engine."""

    @staticmethod
    def evaluate(
        db: Session, api_key: ApiKey, flag_key: str, user: EvaluationUser
    ) -> EvaluationResponse:
        """Evaluate a flag for the API key's organization and environment."""

        flag = db.scalar(
            select(Flag)
            .join(Project)
            .options(joinedload(Flag.project))
            .where(
                Flag.key == flag_key,
                Project.organization_id == api_key.organization_id,
            )
        )
        if flag is None:
            return EvaluationResponse(flag_key=flag_key, value=False, reason="not_found")

        config = db.scalar(
            select(FlagEnvironmentConfig).where(
                FlagEnvironmentConfig.flag_id == flag.id,
                FlagEnvironmentConfig.environment == api_key.environment,
            )
        )
        if config is None:
            return EvaluationResponse(
                flag_key=flag_key, value=flag.off_value, reason="not_found"
            )

        try:
            flag_config = EvaluationService._to_flag_config(flag, config)
            result = EvaluationEngine().evaluate(
                flag_config,
                EvalUser(key=user.key, attributes=user.attributes),
            )
        except (AttributeError, TypeError, ValueError):
            return EvaluationResponse(
                flag_key=flag_key, value=flag.off_value, reason="evaluation_error"
            )

        return EvaluationResponse(
            flag_key=flag_key,
            value=result.value,
            reason=result.reason,
        )

    @staticmethod
    def _to_flag_config(
        flag: Flag, config: FlagEnvironmentConfig
    ) -> FlagConfig:
        rule = None
        rule_values = (
            config.rule_attribute,
            config.rule_operator,
            config.rule_value,
        )
        if any(value is not None for value in rule_values):
            if not all(isinstance(value, str) and value for value in rule_values):
                raise ValueError("Malformed targeting rule")
            rule = TargetingRule(
                attribute=config.rule_attribute,
                operator=config.rule_operator,
                value=config.rule_value,
            )

        return FlagConfig(
            flag_key=flag.key,
            enabled=config.enabled,
            rollout_percentage=config.rollout_percentage,
            rule=rule,
            on_value=flag.on_value,
            off_value=flag.off_value,
        )
