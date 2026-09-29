"""
SAFETY: this script calls Base.metadata.drop_all() / create_all() on
whatever DATABASE_URL resolves to. It refuses to run unless that URL
contains "test", so it can never touch your real dev database.

Usage:
    DATABASE_URL="$TEST_DATABASE_URL" python benchmarks/query_count.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings

if "test" not in settings.database_url:
    raise SystemExit(
        "Refusing to run: DATABASE_URL does not look like a test database "
        f"(got: {settings.database_url}).\n"
        'Run with:  DATABASE_URL="$TEST_DATABASE_URL" python benchmarks/query_count.py'
    )

from sqlalchemy import event
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.cache import cache

# --- query counter -----------------------------------------------------

query_count = 0


@event.listens_for(engine, "before_cursor_execute")
def _count_queries(conn, cursor, statement, parameters, context, executemany):
    global query_count
    query_count += 1


def reset_schema() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed(client: TestClient) -> tuple[str, str]:
    """Create one org/project/flag/api-key. Returns (flag_key, raw_api_key)."""

    signup = client.post(
        "/auth/signup",
        json={"email": "bench@example.com", "password": "correct-horse-battery-staple"},
    )
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org = client.post("/orgs", json={"name": "Bench Org"}, headers=headers).json()
    project = client.post(
        f"/orgs/{org['id']}/projects",
        json={"name": "Bench Project", "key": "bench"},
        headers=headers,
    ).json()
    flag = client.post(
        f"/projects/{project['id']}/flags",
        json={"key": "bench_flag", "name": "Bench Flag"},
        headers=headers,
    ).json()
    client.patch(
        f"/flags/{flag['id']}/environments/production/toggle",
        json={"enabled": True},
        headers=headers,
    )
    api_key = client.post(
        f"/orgs/{org['id']}/api-keys",
        json={"environment": "production"},
        headers=headers,
    ).json()

    return "bench_flag", api_key["raw_key"]


def run_evaluations(
    client: TestClient, flag_key: str, raw_key: str, n: int, force_cold: bool
) -> None:
    headers = {"Authorization": f"ApiKey {raw_key}"}
    body = {"user": {"key": "user-bench", "attributes": {}}}

    for _ in range(n):
        if force_cold:
            cache._store.clear()
        client.post(f"/evaluate/{flag_key}", json=body, headers=headers)


def main() -> None:
    global query_count

    reset_schema()
    client = TestClient(app)
    flag_key, raw_key = seed(client)

    n = 20000

    # Cold: clear the cache before every single call, forcing the full
    # api-key-auth + flag-lookup + config-lookup round trip each time.
    query_count = 0
    run_evaluations(client, flag_key, raw_key, n, force_cold=True)
    cold_total = query_count
    cold_per_request = cold_total / n

    # Warm: one call to populate the cache, then let the TTL cache do
    # its job for the rest (this is the steady-state production case).
    cache._store.clear()
    run_evaluations(client, flag_key, raw_key, 1, force_cold=False)  # warm-up
    query_count = 0  # reset AFTER warm-up so it isn't counted
    run_evaluations(client, flag_key, raw_key, n - 1, force_cold=False)
    warm_total = query_count
    warm_per_request = warm_total / (n - 1)

    reset_schema()  # leave the test database clean for pytest

    print(f"Requests per scenario: {n}")
    print(f"Cold cache: {cold_total} queries total -> {cold_per_request:.1f} queries/request")
    print(f"Warm cache: {warm_total} queries total -> {warm_per_request:.2f} queries/request")
    if cold_per_request > 0:
        reduction = (1 - warm_per_request / cold_per_request) * 100
        print(f"Reduction: {reduction:.0f}% fewer DB queries per evaluation with a warm cache")


if __name__ == "__main__":
    main()