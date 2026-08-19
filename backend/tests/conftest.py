"""
Shared fixtures for the backend suite.

Tests run against SQLite in memory: they're fast, need no infrastructure,
and isolate each case. The relevant dialect differences (trigram indexes,
PostgreSQL-specific types) live in the migration, not in application code,
so they don't affect what's exercised here.

Authentication is **not** mocked: test clients really sign in against the
real endpoint. Replacing it with an override would mean the suite stops
covering exactly the most delicate part of the system.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Rol, Usuario
from app.security import hashear_contrasena
from app.services import limitador

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

CONTRASENA_DE_PRUEBA = "contrasena-de-prueba-1234"
CORREO_ADMIN = "admin@example.com"
CORREO_OPERADOR = "operador@example.com"


@event.listens_for(engine, "connect")
def _activar_claves_foraneas(conexion_dbapi, _registro):
    """
    SQLite ignores foreign keys unless explicitly requested.

    Without this, tests wouldn't catch an integrity violation that
    PostgreSQL would reject in production.
    """
    cursor = conexion_dbapi.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    """Clean database, with the two test users already seeded."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Every test starts with the attempt counters at zero; otherwise a
    # brute-force test would leave the following ones locked out.
    limitador.reiniciar_almacen(limitador.AlmacenEnMemoria())

    db = TestingSessionLocal()
    db.add_all(
        [
            Usuario(
                correo_electronico=CORREO_ADMIN,
                nombre="Admina de Prueba",
                contrasena_hash=hashear_contrasena(CONTRASENA_DE_PRUEBA),
                rol=Rol.ADMIN,
            ),
            Usuario(
                correo_electronico=CORREO_OPERADOR,
                nombre="Operadora de Prueba",
                contrasena_hash=hashear_contrasena(CONTRASENA_DE_PRUEBA),
                rol=Rol.OPERADOR,
            ),
        ]
    )
    db.commit()

    try:
        yield db
    finally:
        db.close()
        limitador.reiniciar_almacen(None)


@pytest.fixture(name="fabrica_de_clientes")
def fabrica_de_clientes_fixture(session):
    """
    Creates independent HTTP clients against the same database.

    Each client carries its own cookie store. Sharing a single instance
    would make signing in as the administrator overwrite the operator's
    session, and the role tests would stop testing anything.
    """
    creados = []

    def _obtener_db():
        yield session

    app.dependency_overrides[get_db] = _obtener_db

    def crear(correo: str | None = None) -> TestClient:
        cliente = TestClient(app)
        cliente.__enter__()
        creados.append(cliente)
        if correo is not None:
            respuesta = cliente.post(
                "/api/v1/auth/token",
                data={"username": correo, "password": CONTRASENA_DE_PRUEBA},
            )
            assert respuesta.status_code == 200, respuesta.text
        return cliente

    yield crear

    for cliente in creados:
        cliente.__exit__(None, None, None)
    app.dependency_overrides.clear()


@pytest.fixture(name="client_anonimo")
def client_anonimo_fixture(fabrica_de_clientes):
    """Client with no session signed in."""
    return fabrica_de_clientes()


@pytest.fixture(name="client")
def client_fixture(fabrica_de_clientes):
    """Client authenticated with the `operador` role, the usual case."""
    return fabrica_de_clientes(CORREO_OPERADOR)


@pytest.fixture(name="client_admin")
def client_admin_fixture(fabrica_de_clientes):
    """Client authenticated with the `admin` role."""
    return fabrica_de_clientes(CORREO_ADMIN)
