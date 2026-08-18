"""
Configuración de SQLAlchemy: motor y sesión de base de datos.
"""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# ---------------------------------------------------------------------------
# Motor y fábrica de sesiones con pooling dinámico según el dialecto de BD
# ---------------------------------------------------------------------------

engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}

# El pool de conexiones avanzado es propio de PostgreSQL
if settings.database_url.startswith("postgresql"):
    engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 3600})

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Clase base para los modelos ORM
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos."""

    pass


# ---------------------------------------------------------------------------
# Dependencia de FastAPI para inyectar la sesión de BD
# ---------------------------------------------------------------------------


def get_db():
    """Generador que provee una sesión de BD y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
