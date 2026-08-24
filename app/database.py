"""Synchronous SQLAlchemy database setup and session dependency."""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request completes."""

    db = SessionLocal()
    logger.info("Database session created")
    try:
        yield db
    finally:
        db.close()
        logger.info("Database session closed")
