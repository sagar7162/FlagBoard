"""Unit tests for evaluation and API-key cache behavior."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.auth.dependencies import get_api_key_context, hash_api_key
from app.cache import (
    SimpleTTLCache,
    api_key_cache_key,
    flag_lookup_cache_key,
)
from app.models import ApiKey, FlagEnvironmentConfig
from app.schemas import EvaluationUser
from app.services.evaluation_service import EvaluationService


def test_evaluation_cache_skips_flag_and_config_queries_on_second_call():
    organization_id = uuid4()
    flag_id = uuid4()
    api_key = ApiKey(
        id=uuid4(),
        organization_id=organization_id,
        environment="production",
        hashed_key="hashed",
        key_prefix="ffb_test",
    )
    flag = SimpleNamespace(
        id=flag_id,
        organization_id=organization_id,
        key="checkout",
        on_value=True,
        off_value=False,
    )
    config = FlagEnvironmentConfig(
        flag_id=flag_id,
        environment="production",
        enabled=True,
    )
    cache = SimpleTTLCache()

    with (
        patch(
            "app.services.evaluation_service.FlagRepository.get_by_organization_and_key",
            return_value=flag,
        ) as get_flag,
        patch(
            "app.services.evaluation_service.EvaluationRepository.get_config",
            return_value=config,
        ) as get_config,
    ):
        first = EvaluationService.evaluate(
            SimpleNamespace(),
            api_key,
            "checkout",
            EvaluationUser(key="user-123"),
            cache,
        )
        second = EvaluationService.evaluate(
            SimpleNamespace(),
            api_key,
            "checkout",
            EvaluationUser(key="user-123"),
            cache,
        )

    assert first.value is True
    assert second.value is True
    get_flag.assert_called_once()
    get_config.assert_called_once()


def test_api_key_cache_skips_second_database_lookup():
    raw_key = f"ffb_{uuid4().hex}"
    hashed_key = hash_api_key(raw_key)
    cache_key = api_key_cache_key(hashed_key)
    api_key = ApiKey(
        id=uuid4(),
        organization_id=uuid4(),
        environment="production",
        hashed_key=hashed_key,
        key_prefix=raw_key[:12],
    )

    from app.cache import cache

    cache.invalidate(cache_key)
    db = SimpleNamespace()
    try:
        with patch(
            "app.auth.dependencies.ApiKeyRepository.get_active_by_hash",
            return_value=api_key,
        ) as get_api_key:
            first = get_api_key_context(f"ApiKey {raw_key}", db)
            second = get_api_key_context(f"ApiKey {raw_key}", db)

        assert first is api_key
        assert second is api_key
        get_api_key.assert_called_once_with(db, hashed_key)
    finally:
        cache.invalidate(cache_key)
