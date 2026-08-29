"""FastAPI dependencies for JWT and evaluation API-key authentication."""

import hashlib
import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import verify_access_token
from app.config import settings
from app.database import get_db
from app.models import ApiKey, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
authorization_header = APIKeyHeader(name="Authorization", auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    """Validate the Bearer JWT and return the corresponding database user."""

    try:
        payload = verify_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("Token subject is missing")
        user_id = UUID(subject)
    except (TypeError, ValueError):
        raise _unauthorized() from None

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()

    return user


def hash_api_key(api_key: str) -> str:
    """Return the peppered HMAC used to store and look up an API key."""

    return hmac.new(
        settings.api_key_pepper.encode("utf-8"),
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def get_api_key_context(
    authorization: Annotated[str | None, Depends(authorization_header)],
    db: DbSession,
) -> ApiKey:
    """Validate ``Authorization: ApiKey <key>`` and return its active record."""

    if not authorization:
        raise _api_key_unauthorized()

    scheme, _, raw_key = authorization.partition(" ")
    if scheme.lower() != "apikey" or not raw_key.strip():
        raise _api_key_unauthorized()

    api_key = db.scalar(
        select(ApiKey).where(
            ApiKey.hashed_key == hash_api_key(raw_key.strip()),
            ApiKey.revoked_at.is_(None),
        )
    )
    if api_key is None:
        raise _api_key_unauthorized()

    return api_key


def get_current_api_key(
    authorization: Annotated[str | None, Depends(authorization_header)],
    db: DbSession,
) -> ApiKey:
    """Alias for the evaluation API-key dependency."""

    return get_api_key_context(authorization, db)


def _api_key_unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
