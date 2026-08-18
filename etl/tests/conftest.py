"""
Fixtures de la suite del ETL.

Las pruebas de carga necesitan un esquema real. En lugar de redefinirlo aqui
(lo que crearia una segunda fuente de verdad que acabaria divergiendo de las
migraciones), se construye a partir de los modelos del backend, que son los
mismos que Alembic materializa. Si el backend no esta instalado, las pruebas de
carga se omiten y quedan las de transformacion, que son puras.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

RAIZ = Path(__file__).resolve().parents[2]

# La llave solo cifra datos de prueba; el backend valida su formato al importarse.
os.environ.setdefault("TRAMEX_FERNET_KEY", "CxNCUQhBIDIRsETw8i-dfZBdmcnh6YX43VWS-9txMY4=")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


def _cargar_metadatos():
    """Devuelve los metadatos del backend, o None si no esta disponible."""
    if str(RAIZ / "backend") not in sys.path:
        sys.path.insert(0, str(RAIZ / "backend"))
    try:
        import app.models  # noqa: F401  (registra los modelos en el metadata)
        from app.database import Base
    except Exception:
        return None
    return Base.metadata


@pytest.fixture(name="engine")
def engine_fixture():
    """Base SQLite en memoria con el esquema real del proyecto."""
    metadatos = _cargar_metadatos()
    if metadatos is None:
        pytest.skip("El paquete del backend no esta instalado; se omiten las pruebas de carga.")

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
