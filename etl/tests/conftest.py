"""
Fixtures for the ETL suite.

The load tests need a real schema. Instead of redefining it here (which
would create a second source of truth that would eventually drift from the
migrations), it's built from the backend's models, the same ones Alembic
materializes. If the backend isn't installed, the load tests are skipped and
the transformation ones remain, since those are pure.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

RAIZ = Path(__file__).resolve().parents[2]

# The key only encrypts test data; the backend validates its format on import.
os.environ.setdefault("TRAMEX_FERNET_KEY", "CxNCUQhBIDIRsETw8i-dfZBdmcnh6YX43VWS-9txMY4=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


def _cargar_metadatos():
    """Returns the backend's metadata, or None if it isn't available."""
    if str(RAIZ / "backend") not in sys.path:
        sys.path.insert(0, str(RAIZ / "backend"))
    try:
        import app.models  # noqa: F401  (registers the models on the metadata)
        from app.database import Base
    except Exception:
        return None
    return Base.metadata


@pytest.fixture(name="engine")
def engine_fixture():
    """In-memory SQLite database with the project's real schema."""
    metadatos = _cargar_metadatos()
    if metadatos is None:
        pytest.skip("The backend package is not installed; load tests are skipped.")

    motor = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(motor, "connect")
    def _claves_foraneas(conexion_dbapi, _registro):
        cursor = conexion_dbapi.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    metadatos.create_all(motor)
    try:
        yield motor
    finally:
        motor.dispose()


@pytest.fixture(name="fernet")
def fernet_fixture():
    from cryptography.fernet import Fernet

    return Fernet(os.environ["TRAMEX_FERNET_KEY"].encode())
