"""Tests for password security, authentication, and current-user resolution."""

import os
import unittest
from datetime import timedelta
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/flagboard")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-bytes-long")
os.environ.setdefault("API_KEY_PEPPER", "test-pepper")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')

from fastapi import HTTPException

from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_access_token,
    verify_password,
)
from app.models import User
from app.schemas import UserCreate, UserLogin
from app.services.auth_service import AuthService


class FakeSession:
    """Small session double for auth tests that do not need PostgreSQL."""

    def __init__(self, user: User | None = None):
        self.user = user
        self.added: User | None = None

    def scalar(self, statement):
        return self.user

    def add(self, user: User) -> None:
        self.added = user

    def commit(self) -> None:
        if self.added is not None and self.added.id is None:
            self.added.id = uuid4()

    def refresh(self, user: User) -> None:
        if user.id is None:
            user.id = uuid4()

    def get(self, model, user_id: UUID) -> User | None:
        assert model is User
        return self.user if self.user is not None and self.user.id == user_id else None


class AuthTests(unittest.TestCase):
    def test_password_hash_round_trip(self):
        password = "a password longer than bcrypt normally accepts " * 3
        password_hash = hash_password(password)

        self.assertNotEqual(password, password_hash)
        self.assertTrue(verify_password(password, password_hash))
        self.assertFalse(verify_password("wrong password", password_hash))

    def test_access_token_round_trip_and_expiry(self):
        token = create_access_token({"sub": "user-123"})
        self.assertEqual(verify_access_token(token)["sub"], "user-123")

        expired_token = create_access_token(
            {"sub": "user-123"}, expires_delta=timedelta(seconds=-1)
        )
        with self.assertRaisesRegex(ValueError, "Invalid or expired access token"):
            verify_access_token(expired_token)

    def test_signup_normalizes_email_hashes_password_and_returns_token(self):
        db = FakeSession()

        token = AuthService.signup(
            db,
            UserCreate(email="  User@Example.COM ", password="secret"),
        )

        self.assertIsNotNone(db.added)
        self.assertEqual(db.added.email, "user@example.com")
        self.assertTrue(verify_password("secret", db.added.password_hash))
        self.assertEqual(
            verify_access_token(token.access_token)["sub"], str(db.added.id)
        )

    def test_signup_rejects_duplicate_email(self):
        existing_user = User(
            id=uuid4(),
            email="user@example.com",
            password_hash=hash_password("secret"),
        )

        with self.assertRaisesRegex(ValueError, "Email already registered"):
            AuthService.signup(
                FakeSession(existing_user),
                UserCreate(email="USER@example.com", password="secret"),
            )

    def test_login_accepts_normalized_email_and_rejects_wrong_password(self):
        existing_user = User(
            id=uuid4(),
            email="user@example.com",
            password_hash=hash_password("secret"),
        )

        token = AuthService.login(
            FakeSession(existing_user),
            UserLogin(email=" USER@EXAMPLE.COM ", password="secret"),
        )
        self.assertEqual(
            verify_access_token(token.access_token)["sub"], str(existing_user.id)
        )

        with self.assertRaisesRegex(ValueError, "Invalid email or password"):
            AuthService.login(
                FakeSession(existing_user),
                UserLogin(email="user@example.com", password="wrong"),
            )

    def test_get_current_user_returns_user_and_rejects_invalid_token(self):
        user = User(id=uuid4(), email="user@example.com", password_hash="hash")
        db = FakeSession(user)
        token = create_access_token({"sub": str(user.id)})

        self.assertIs(get_current_user(token, db), user)

        with self.assertRaises(HTTPException) as context:
            get_current_user("invalid-token", db)
        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.headers["WWW-Authenticate"], "Bearer")


if __name__ == "__main__":
    unittest.main()
