"""Unit tests for the pure feature-flag evaluation engine."""

import unittest

from app.engine.evaluator import EvalUser, EvaluationEngine, FlagConfig, TargetingRule


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.engine = EvaluationEngine()
        self.user = EvalUser(key="user-123", attributes={"plan": "pro"})

    def test_disabled_flag_returns_flag_disabled(self):
        result = self.engine.evaluate(
            FlagConfig(flag_key="checkout", enabled=False),
            self.user,
        )

        self.assertEqual((result.value, result.reason), (False, "flag_disabled"))

    def test_matching_rule_returns_rule_match_before_rollout(self):
        result = self.engine.evaluate(
            FlagConfig(
                flag_key="checkout",
                enabled=True,
                rollout_percentage=0,
                rule=TargetingRule("plan", "equals", "pro"),
            ),
            self.user,
        )

        self.assertEqual((result.value, result.reason), (True, "rule_match"))

    def test_full_rollout_returns_rollout(self):
        result = self.engine.evaluate(
            FlagConfig(flag_key="checkout", enabled=True, rollout_percentage=100),
            self.user,
        )

        self.assertEqual((result.value, result.reason), (True, "rollout"))

    def test_zero_rollout_returns_rollout_excluded(self):
        result = self.engine.evaluate(
            FlagConfig(flag_key="checkout", enabled=True, rollout_percentage=0),
            self.user,
        )

        self.assertEqual((result.value, result.reason), (False, "rollout_excluded"))

    def test_enabled_flag_without_targeting_returns_default_on(self):
        result = self.engine.evaluate(
            FlagConfig(flag_key="checkout", enabled=True),
            self.user,
        )

        self.assertEqual((result.value, result.reason), (True, "default_on"))

    def test_missing_rule_attribute_does_not_match(self):
        result = self.engine.evaluate(
            FlagConfig(
                flag_key="checkout",
                enabled=True,
                rule=TargetingRule("plan", "equals", "pro"),
            ),
            EvalUser(key="user-456"),
        )

        self.assertEqual((result.value, result.reason), (True, "default_on"))


if __name__ == "__main__":
    unittest.main()
