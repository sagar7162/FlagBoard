"""Database-backed flag evaluation orchestration."""

from sqlalchemy.orm import Session

from app.cache import (
    CachedFlag,
    SimpleTTLCache,
    cache,
    flag_config_cache_key,
    flag_lookup_cache_key,
)
from app.engine.evaluator import (
    EvalUser,
    EvaluationEngine,
    FlagConfig,
    TargetingRule,
)
from app.models import ApiKey, FlagEnvironmentConfig
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.flag_repository import FlagRepository
from app.schemas import EvaluationResponse, EvaluationUser


class EvaluationService:
    """Resolve organization-scoped flags using the pure evaluation engine."""

    @staticmethod
    def evaluate(
        db: Session,
        api_key: ApiKey,
        flag_key: str,
        user: EvaluationUser,
        cache_store: SimpleTTLCache = cache,
    ) -> EvaluationResponse:
        """Evaluate a flag for the API key's organization and environment."""

        lookup_key = flag_lookup_cache_key(api_key.organization_id, flag_key)
        cached_flag = cache_store.get(lookup_key)
        if cached_flag is None:
            flag = FlagRepository.get_by_organization_and_key(
                db, api_key.organization_id, flag_key
            )
            if flag is None:
                return EvaluationResponse(
                    flag_key=flag_key, value=False, reason="not_found"
                )
            cached_flag = CachedFlag(
                id=flag.id,
                organization_id=flag.organization_id,
                key=flag.key,
                on_value=flag.on_value,
                off_value=flag.off_value,
            )
            cache_store.set(lookup_key, cached_flag)

        if not isinstance(cached_flag, CachedFlag):
            return EvaluationResponse(flag_key=flag_key, value=False, reason="not_found")

        cache_key = flag_config_cache_key(cached_flag.id, api_key.environment)
        flag_config = cache_store.get(cache_key)
        if flag_config is None:
            config = EvaluationRepository.get_config(
                db, cached_flag.id, api_key.environment
            )
            if config is None:
                return EvaluationResponse(
                    flag_key=flag_key,
                    value=cached_flag.off_value,
                    reason="not_found",
                )

            try:
                flag_config = EvaluationService._to_flag_config(cached_flag, config)
            except (AttributeError, TypeError, ValueError):
                return EvaluationResponse(
                    flag_key=flag_key,
                    value=cached_flag.off_value,
                    reason="evaluation_error",
                )
            cache_store.set(cache_key, flag_config)

        try:
            result = EvaluationEngine().evaluate(
                flag_config,
                EvalUser(key=user.key, attributes=user.attributes),
            )
        except (AttributeError, TypeError, ValueError):
            return EvaluationResponse(
                flag_key=flag_key,
                value=cached_flag.off_value,
                reason="evaluation_error",
            )

        return EvaluationResponse(
            flag_key=flag_key,
            value=result.value,
            reason=result.reason,
        )

    @staticmethod
    def _to_flag_config(
        flag: CachedFlag, config: FlagEnvironmentConfig
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
