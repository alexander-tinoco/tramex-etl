"""
Fixtures compartidas de la suite del backend.

Las pruebas corren contra SQLite en memoria: son rapidas, no requieren
infraestructura y aislan cada caso. Las diferencias de dialecto relevantes
(indices de trigramas, tipos de PostgreSQL) viven en la migracion, no en el
codigo de aplicacion, por lo que no afectan a lo que aqui se ejercita.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.security import get_current_user

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _activar_claves_foraneas(conexion_dbapi, _registro):
    """
    SQLite ignora las claves foraneas salvo que se pidan explicitamente.

    Sin esto las pruebas no detectarian una violacion de integridad que
    PostgreSQL si rechazaria en produccion.
    """
    cursor = conexion_dbapi.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    """Base limpia para cada prueba."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture(session):
    """Cliente HTTP con la base en memoria y la autenticacion simulada."""

    def _obtener_db():
        yield session

    app.dependency_overrides[get_db] = _obtener_db
    app.dependency_overrides[get_current_user] = lambda: "usuario_de_prueba"

    with TestClient(app) as cliente:
        yield cliente

    app.dependency_overrides.clear()


@pytest.fixture(name="client_sin_auth")
def client_sin_auth_fixture(session):
    """Cliente HTTP sin simular la autenticacion, para probar el rechazo 401."""

    def _obtener_db():
        yield session

    app.dependency_overrides[get_db] = _obtener_db

    with TestClient(app) as cliente:
        yield cliente

    app.dependency_overrides.clear()
