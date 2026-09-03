"""Happy-path and tenant-isolation tests for flag APIs."""

import unittest
from uuid import uuid4

from fastapi import HTTPException

from app.models import (
    ApiKey,
    AuditLogEntry,
    Flag,
    FlagEnvironmentConfig,
    Membership,
    Organization,
    Project,
    User,
)
from app.routers.evaluate_router import evaluate_flag
from app.routers.flags_router import (
    create_flag,
    toggle_flag,
    update_rollout,
    update_rule,
)
from app.schemas import (
    EvaluationRequest,
    EvaluationUser,
    FlagCreate,
    FlagRuleUpdate,
    FlagRolloutUpdate,
    FlagToggle,
)


class FakeSession:
    """Small database-session double for route/service integration tests."""

    def __init__(self, get_value=None, scalar_values=()):
        self.get_value = get_value
        self.scalar_values = iter(scalar_values)
        self.added = []

    def get(self, model, identifier):
        return self.get_value

    def scalar(self, statement):
        return next(self.scalar_values)

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added.extend(values)

    def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    def commit(self):
        self.flush()

    def refresh(self, value):
        self.flush()

    def rollback(self):
        pass


class FlagsApiTests(unittest.TestCase):
    def setUp(self):
        self.user = User(id=uuid4(), email="owner@example.com", password_hash="hash")
        self.other_user = User(
            id=uuid4(), email="other@example.com", password_hash="hash"
        )
        self.organization = Organization(id=uuid4(), name="Acme", slug="acme")
        self.project = Project(
            id=uuid4(),
            organization_id=self.organization.id,
            name="Web",
            key="web",
        )
        self.membership = Membership(
            id=uuid4(),
            user_id=self.user.id,
            organization_id=self.organization.id,
            role="owner",
        )

    def test_flag_happy_path_create_toggle_rollout_rule_and_evaluate(self):
        create_db = FakeSession(
            get_value=self.project,
            scalar_values=[self.membership, None],
        )
        flag = create_flag(
            self.project.id,
            FlagCreate(key="checkout", name="New checkout"),
            create_db,
            self.user,
        )
        flag.on_value = True
        flag.off_value = False
        self.assertEqual(flag.key, "checkout")
        configs = [
            value for value in create_db.added if isinstance(value, FlagEnvironmentConfig)
        ]
        self.assertEqual(
            {config.environment for config in configs},
            {"development", "staging", "production"},
        )
        audit_entries = [
            value for value in create_db.added if isinstance(value, AuditLogEntry)
        ]
        self.assertEqual(len(audit_entries), 1)
        self.assertEqual(audit_entries[0].action, "flag_created")

        flag.project = self.project
        config = FlagEnvironmentConfig(
            id=uuid4(),
            flag_id=flag.id,
            environment="production",
            enabled=False,
        )

        toggle_flag(
            flag.id,
            "production",
            FlagToggle(enabled=True),
            FakeSession(scalar_values=[flag, self.membership, config]),
            self.user,
        )
        self.assertTrue(config.enabled)

        update_rollout(
            flag.id,
            "production",
            FlagRolloutUpdate(percentage=50),
            FakeSession(scalar_values=[flag, self.membership, config]),
            self.user,
        )
        self.assertEqual(config.rollout_percentage, 50)

        update_rule(
            flag.id,
            "production",
            FlagRuleUpdate(attribute="plan", operator="equals", value="pro"),
            FakeSession(scalar_values=[flag, self.membership, config]),
            self.user,
        )
        self.assertEqual(
            (config.rule_attribute, config.rule_operator, config.rule_value),
            ("plan", "equals", "pro"),
        )

        api_key = ApiKey(
            id=uuid4(),
            organization_id=self.organization.id,
            environment="production",
            hashed_key="hashed",
            key_prefix="ffb_test",
        )
        evaluation = evaluate_flag(
            "checkout",
            EvaluationRequest(
                user=EvaluationUser(key="user-123", attributes={"plan": "pro"})
            ),
            FakeSession(scalar_values=[flag, config]),
            api_key,
        )
        self.assertEqual(
            (evaluation.value, evaluation.reason), (True, "rule_match")
        )

    def test_user_from_another_tenant_cannot_create_flag(self):
        db = FakeSession(get_value=self.project, scalar_values=[None])

        with self.assertRaises(HTTPException) as context:
            create_flag(
                self.project.id,
                FlagCreate(key="private", name="Private flag"),
                db,
                self.other_user,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_api_key_from_another_tenant_cannot_evaluate_flag(self):
        flag = Flag(
            id=uuid4(),
            project_id=self.project.id,
            key="checkout",
            name="Checkout",
            created_by=self.user.id,
        )
        api_key = ApiKey(
            id=uuid4(),
            organization_id=uuid4(),
            environment="production",
            hashed_key="hashed",
            key_prefix="ffb_test",
        )

        result = evaluate_flag(
            "checkout",
            EvaluationRequest(user=EvaluationUser(key="user-123")),
            FakeSession(scalar_values=[None]),
            api_key,
        )

        self.assertEqual(
            (result.value, result.reason), (False, "not_found")
        )


if __name__ == "__main__":
    unittest.main()
