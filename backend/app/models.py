"""
Modelos ORM de SQLAlchemy que mapean las tablas existentes de PostgreSQL.

Las tablas ya existen en la base de datos; estos modelos reflejan
su estructura exacta para poder operar sobre ellas con el ORM.
"""

from datetime import date, datetime

from sqlalchemy import Date, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------------------------------------------------------------------------
# master_tramex
# ---------------------------------------------------------------------------

class MasterTramex(Base):
    """Tabla principal de trámites."""

    __tablename__ = "master_tramex"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    id_solicitud: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    tramite: Mapped[str | None] = mapped_column(Text, nullable=True)
    cita: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# global_entry
# ---------------------------------------------------------------------------

class GlobalEntry(Base):
    """Tabla de registros de Global Entry."""

    __tablename__ = "global_entry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# pasaportes
# ---------------------------------------------------------------------------

class Pasaporte(Base):
    """Tabla de trámites de pasaportes."""

    __tablename__ = "pasaportes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    lugar_cita: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_cita: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_cita_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# canada
# ---------------------------------------------------------------------------

class Canada(Base):
    """Tabla de trámites de Canadá."""

    __tablename__ = "canada"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    cuenta_ircc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
