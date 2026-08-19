"""
SQLAlchemy configuration: database engine and session.
"""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# Engine and session factory, with dynamic pooling based on the DB dialect
# ---------------------------------------------------------------------------

engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}

# The advanced connection pool is PostgreSQL-specific
if settings.database_url.startswith("postgresql"):
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 3600})

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Base class for the ORM models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base class for all models."""

    pass


# ---------------------------------------------------------------------------
# FastAPI dependency to inject the DB session
# ---------------------------------------------------------------------------


def get_db():
    """Generator that provides a DB session and closes it when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
