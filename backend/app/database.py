"""
Configuración de SQLAlchemy: motor y sesión de base de datos.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

# ---------------------------------------------------------------------------
# Motor y fábrica de sesiones
# ---------------------------------------------------------------------------

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

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
