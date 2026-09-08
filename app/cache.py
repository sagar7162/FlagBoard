"""Small in-process TTL cache for compiled flag configurations."""

import time
from dataclasses import dataclass
from uuid import UUID

from app.config import settings


@dataclass(frozen=True)
class CachedFlag:
    """The flag fields needed to build an evaluation configuration."""

    id: UUID
    organization_id: UUID
    key: str
    on_value: bool
    off_value: bool


class SimpleTTLCache:
    """Cache flag configurations for one application process.

    This cache assumes a single application process owns the dictionary. It is
    intentionally in-memory; a shared cache such as Redis can replace it if
    the service is later run across multiple processes.
    """

    def __init__(self, ttl_seconds: int = 30):
        if ttl_seconds < 0:
            raise ValueError("TTL must be non-negative")
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> object | None:
        """Return a cached configuration, or ``None`` on a miss/expiry."""

        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: object) -> None:
        """Store a configuration until the cache entry's TTL expires."""

        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def invalidate(self, key: str) -> None:
        """Remove a cached entry if it exists."""

        self._store.pop(key, None)


cache = SimpleTTLCache(settings.cache_ttl_seconds)


def flag_lookup_cache_key(organization_id: UUID, flag_key: str) -> str:
    """Return the cache key for an organization-scoped flag lookup."""

    return f"flag-lookup:{organization_id}:{flag_key}"


def flag_config_cache_key(flag_id: UUID, environment: str) -> str:
    """Return the cache key for one flag environment configuration."""

    return f"flag-config:{flag_id}:{environment}"


def api_key_cache_key(hashed_key: str) -> str:
    """Return the cache key for an API-key authentication lookup."""

    return f"api-key:{hashed_key}"
