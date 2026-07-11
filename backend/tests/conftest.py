import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.security import get_current_user

# ---------------------------------------------------------------------------
# Base de datos en memoria para pruebas aisladas
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    """Crea las tablas antes de cada test y las elimina al terminar."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(name="client")
def client_fixture(session):
    """
    Cliente de pruebas con dos overrides:
    - get_db  → sesión de SQLite en memoria
    - get_current_user → usuario de prueba (bypass de JWT)
    """
    def override_get_db():
        try:
            yield session
        finally:
            pass

    def override_get_current_user():
        return "test_user"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield TestClient(app)

    app.dependency_overrides.clear()
