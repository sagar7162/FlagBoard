"""Password hashing and JWT helpers."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings


ALGORITHM = "HS256"


def _password_bytes(password: str) -> bytes:
    """Normalize passwords before bcrypt's 72-byte input limit."""

    return sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage."""

    password_bytes = _password_bytes(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches its stored hash."""

    return bcrypt.checkpw(
        _password_bytes(password), password_hash.encode("utf-8")
    )


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT containing the supplied claims."""

    payload = data.copy()
    expires_at = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expiry_hours)
    )
    payload["exp"] = expires_at

    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising ``ValueError`` if it is invalid."""

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token") from exc

    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    """Compatibility alias for token verification at dependency call sites."""

    return verify_access_token(token)
