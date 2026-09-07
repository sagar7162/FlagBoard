"""Shared fixtures for HTTP integration tests against PostgreSQL."""

import os
import sys
from collections.abc import Generator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    """Create a schema on the explicitly configured test PostgreSQL database."""

    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must point to a separate PostgreSQL test database; "
            "refusing to run integration tests without one"
        )
    if not database_url.startswith("postgresql"):
        raise RuntimeError("TEST_DATABASE_URL must use a PostgreSQL SQLAlchemy URL")
    if database_url == settings.database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be different from DATABASE_URL; "
            "refusing to run against the application database"
        )

    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def client(test_engine) -> Generator[TestClient, None, None]:
    """Return an HTTP client whose requests use the real test database."""

    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
    )

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()
