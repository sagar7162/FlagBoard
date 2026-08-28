"""Deterministic percentage-rollout bucketing."""

import hashlib


def bucket_for(flag_key: str, user_key: str) -> int:
    """Return a deterministic 0-99 bucket for a user and one flag."""

    digest = hashlib.md5(f"{flag_key}:{user_key}".encode()).hexdigest()
    return int(digest, 16) % 100
