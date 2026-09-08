"""Signup and login business logic."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import Token, UserCreate, UserLogin


class AuthService:
    """Handle user registration and authentication."""

    @staticmethod
    def signup(db: Session, user_data: UserCreate) -> Token:
        """Create a user account and return its access token."""

        email = AuthService._normalize_email(user_data.email)
        existing_user = UserRepository.get_by_email(db, email)
        if existing_user is not None:
            raise ValueError("Email already registered")

        user = User(
            email=email,
            password_hash=hash_password(user_data.password),
        )
        try:
            UserRepository.create(db, user)
        except IntegrityError as exc:
            UserRepository.rollback(db)
            raise ValueError("Email already registered") from exc

        return AuthService._token_for(user)

    @staticmethod
    def login(db: Session, user_data: UserLogin) -> Token:
        """Validate credentials and return an access token."""

        email = AuthService._normalize_email(user_data.email)
        user = UserRepository.get_by_email(db, email)
        if user is None or not verify_password(user_data.password, user.password_hash):
            raise ValueError("Invalid email or password")

        return AuthService._token_for(user)

    @staticmethod
    def _token_for(user: User) -> Token:
        return Token(access_token=create_access_token({"sub": str(user.id)}))

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()
