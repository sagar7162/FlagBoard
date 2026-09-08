"""Pure feature-flag evaluation logic."""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.engine.rollout import bucket_for


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetingRule:
    """The single targeting rule supported by the v1 evaluator."""

    attribute: str
    operator: str
    value: str


@dataclass(frozen=True)
class FlagConfig:
    """Runtime configuration needed to evaluate one flag."""

    flag_key: str = ""
    enabled: bool = False
    rollout_percentage: int | None = None
    rule: TargetingRule | None = None
    on_value: bool = True
    off_value: bool = False


@dataclass(frozen=True)
class EvalUser:
    """The user identity and attributes used during evaluation."""

    key: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    """Resolved flag value and the reason for the decision."""

    value: bool
    reason: str


class EvaluationEngine:
    """Evaluate a flag configuration without I/O or framework dependencies."""

    def evaluate(self, flag_config: FlagConfig, user: EvalUser) -> EvaluationResult:
        """Resolve a flag in the documented targeting and rollout order."""

        if not flag_config.enabled:
            return EvaluationResult(flag_config.off_value, "flag_disabled")

        if flag_config.rule is not None:
            if flag_config.rule.operator != "equals":
                logger.warning(
                    "Malformed targeting rule operator for flag %s: %r",
                    flag_config.flag_key,
                    flag_config.rule.operator,
                )
                return EvaluationResult(flag_config.off_value, "evaluation_error")

            if self._rule_matches(flag_config.rule, user):
                return EvaluationResult(flag_config.on_value, "rule_match")

        if flag_config.rollout_percentage is not None:
            bucket = bucket_for(flag_config.flag_key, user.key)
            if bucket < flag_config.rollout_percentage:
                return EvaluationResult(flag_config.on_value, "rollout")
            return EvaluationResult(flag_config.off_value, "rollout_excluded")

        return EvaluationResult(flag_config.on_value, "default_on")

    @staticmethod
    def _rule_matches(rule: TargetingRule | None, user: EvalUser) -> bool:
        if rule is None:
            return False

        attribute_value = user.attributes.get(rule.attribute)
        return attribute_value is not None and attribute_value == rule.value
