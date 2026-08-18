"""
Fixtures compartidas de la suite del backend.

Las pruebas corren contra SQLite en memoria: son rapidas, no requieren
infraestructura y aislan cada caso. Las diferencias de dialecto relevantes
(indices de trigramas, tipos propios de PostgreSQL) viven en la migracion y no
en el codigo de aplicacion, por lo que no afectan a lo que aqui se ejercita.

La autenticacion **no** se simula: los clientes de prueba inician sesion de
verdad contra el endpoint real. Sustituirla por un override haria que la suite
dejara de cubrir justamente la parte mas delicada del sistema.
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
    """Base limpia, con los dos usuarios de prueba ya sembrados."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Cada prueba parte con los contadores de intentos a cero; de lo contrario
    # una prueba de fuerza bruta dejaria bloqueadas a las siguientes.
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
    Crea clientes HTTP independientes sobre la misma base.

    Cada cliente lleva su propio almacen de cookies. Compartir una sola
    instancia haria que iniciar sesion como administradora sobrescribiera la
    sesion de la operadora, y las pruebas de roles dejarian de probar nada.
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
    """Cliente sin sesion iniciada."""
    return fabrica_de_clientes()


@pytest.fixture(name="client")
def client_fixture(fabrica_de_clientes):
    """Cliente autenticado con rol `operador`, que es el uso habitual."""
    return fabrica_de_clientes(CORREO_OPERADOR)


@pytest.fixture(name="client_admin")
def client_admin_fixture(fabrica_de_clientes):
    """Cliente autenticado con rol `admin`."""
    return fabrica_de_clientes(CORREO_ADMIN)
