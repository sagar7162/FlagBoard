"""Signup and login business logic."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import Token, UserCreate, UserLogin


class AuthService:
    """Handle user registration and authentication."""

    @staticmethod
    def signup(db: Session, user_data: UserCreate) -> Token:
        """Create a user account and return its access token."""

        email = AuthService._normalize_email(user_data.email)
        existing_user = db.scalar(select(User).where(User.email == email))
        if existing_user is not None:
            raise ValueError("Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(user_data.password),
        )
        db.add(user)

        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ValueError("Email already registered") from exc

        db.refresh(user)
        return AuthService._token_for(user)

    @staticmethod
    def login(db: Session, user_data: UserLogin) -> Token:
        """Validate credentials and return an access token."""

        email = AuthService._normalize_email(user_data.email)
        user = db.scalar(select(User).where(User.email == email))
        if user is None or not verify_password(user_data.password, user.password_hash):
            raise ValueError("Invalid email or password")

        return AuthService._token_for(user)

    @staticmethod
    def _token_for(user: User) -> Token:
        return Token(access_token=create_access_token({"sub": str(user.id)}))

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()
