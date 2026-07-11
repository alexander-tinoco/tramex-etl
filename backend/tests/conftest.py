import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Asegurar que importemos desde app correctamente agregando el path si fuese necesario,
# pero al correr pytest desde /backend, el working directory ya contiene 'app'.
from app.database import Base, get_db
from app.main import app

# Base de datos en memoria para pruebas rápidas y aisladas
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="session")
def session_fixture():
    # Crear la estructura de la base de datos limpia para cada test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(name="client")
def client_fixture(session):
    def override_get_db():
        try:
            yield session
        finally:
            pass

    # Reemplazar la dependencia de la base de datos real con la de pruebas
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Limpiar override después del test
    del app.dependency_overrides[get_db]
