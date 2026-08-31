"""Small in-process TTL cache for compiled flag configurations."""

import time

from app.engine.evaluator import FlagConfig


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
        self._store: dict[str, tuple[float, FlagConfig]] = {}

    def get(self, key: str) -> FlagConfig | None:
        """Return a cached configuration, or ``None`` on a miss/expiry."""

        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: FlagConfig) -> None:
        """Store a configuration until the cache entry's TTL expires."""

        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def invalidate(self, key: str) -> None:
        """Remove a cached entry if it exists."""

        self._store.pop(key, None)


cache = SimpleTTLCache()
