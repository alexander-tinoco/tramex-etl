"""
SQLAlchemy ORM models.

The relational model revolves around the `Cliente` entity: a person who
contracts the agency can simultaneously have a passport tramite, a Global
Entry one, and a Canada one. In the original spreadsheet that relationship
was implicit (the same name repeated across four different tabs); here it's
explicit via foreign keys.

Conventions shared across all tramite tables:

- `clave_natural`  Stable fingerprint of the fields that identify the record
                   in the source file. It's UNIQUE and lets the ETL be
                   idempotent via `INSERT ... ON CONFLICT DO UPDATE`.
- `hash_fila`      Fingerprint of *all* the plain-text business fields. If it
                   doesn't change between two ETL runs, the row is left
                   untouched (avoids unnecessary rewrites and re-encryption).
- `eliminado_en`   Soft delete. Personal data is never destroyed immediately:
                   it's marked and purged according to the retention policy
                   documented in docs/decisions/0005.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    """Timestamps and soft delete shared by every table."""

    cargado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    eliminado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class RegistroBase(Base, TimestampMixin):
    """
    Abstract base for every table that takes part in the ingestion pipeline.

    Declares the common columns in one place: identifier, name, the two
    identity fingerprints, and the timestamps. It's `__abstract__`, so
    SQLAlchemy doesn't create any table for it.

    Besides avoiding repeating six columns across five models, it exists for
    a typing reason: the generic repositories operate on `eliminado_en`,
    `clave_natural` and `id`, and with the bare declarative base the checker
    can't know those columns exist. With this base, `CRUDBase`'s `TypeVar` is
    bounded to something that does declare them.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    #: Fingerprint of the identifying fields. Target of the ETL's ON CONFLICT.
    clave_natural: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    #: Fingerprint of the full content, to detect whether anything actually changed.
    hash_fila: Mapped[str] = mapped_column(Text, nullable=False)


def indice_trigramas(tabla: str) -> Index:
    """
    Trigram GIN index on the name, for partial-match searches.

    Listings filter with `ILIKE '%text%'`, and a B-tree index can't serve
    that query because the wildcard is at the start: PostgreSQL would end up
    scanning the whole table. `pg_trgm` can resolve it.

    Declared on the model, not only in the migration, so continuous
    integration's drift detection doesn't read it as a stray index. On
    dialects other than PostgreSQL the dialect-specific arguments are
    ignored and it becomes an ordinary index, harmless for tests.
    """
    return Index(
        f"ix_{tabla}_nombre_trgm",
        "nombre",
        postgresql_using="gin",
        postgresql_ops={"nombre": "gin_trgm_ops"},
    )


def indice_clave_natural(tabla: str) -> Index:
    """
    *Partial* unique index on the natural key of active records.

    Uniqueness is deliberately restricted to `eliminado_en IS NULL`. A full
    UNIQUE constraint would prevent keeping history: the original load, which
    did a blind `INSERT`, left duplicate rows in the database, and archiving
    them would still occupy their key and block re-inserting the correct
    version. With the partial index, one active record and any number of
    archived versions of the same identity can coexist.
    """
    return Index(
        f"uq_{tabla}_clave_natural_activa",
        "clave_natural",
        unique=True,
        postgresql_where=text("eliminado_en IS NULL"),
        sqlite_where=text("eliminado_en IS NULL"),
    )


# ---------------------------------------------------------------------------
# clientes — root of the relational model
# ---------------------------------------------------------------------------


class Cliente(RegistroBase):
    """Person who contracts one or more tramites with the agency."""

    __tablename__ = "clientes"
    __table_args__ = (
        indice_clave_natural("clientes"),
        indice_trigramas("clientes"),
    )

    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    master_tramex: Mapped[list["MasterTramex"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )
    global_entry: Mapped[list["GlobalEntry"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )
    pasaportes: Mapped[list["Pasaporte"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )
    canada: Mapped[list["Canada"]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan"
    )

    @property
    def nombre_completo(self) -> str:
        return " ".join(p for p in (self.nombre, self.apellido) if p)


# ---------------------------------------------------------------------------
# master_tramex
# ---------------------------------------------------------------------------


class MasterTramex(RegistroBase):
    """Main tramite (US visa and related processes)."""

    __tablename__ = "master_tramex"
    __table_args__ = (
        Index("ix_master_tramex_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("master_tramex"),
        indice_trigramas("master_tramex"),
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    id_solicitud: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    tramite: Mapped[str | None] = mapped_column(Text, nullable=True)
    cita: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="master_tramex")


# ---------------------------------------------------------------------------
# global_entry
# ---------------------------------------------------------------------------


class GlobalEntry(RegistroBase):
    """Global Entry tramite."""

    __tablename__ = "global_entry"
    __table_args__ = (
        Index("ix_global_entry_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("global_entry"),
        indice_trigramas("global_entry"),
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="global_entry")


# ---------------------------------------------------------------------------
# pasaportes
# ---------------------------------------------------------------------------


class Pasaporte(RegistroBase):
    """Passport issuance or renewal tramite."""

    __tablename__ = "pasaportes"
    __table_args__ = (
        Index("ix_pasaportes_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("pasaportes"),
        indice_trigramas("pasaportes"),
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    lugar_cita: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_cita: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # The source Excel file contains date cells with free-form text ("MARZO").
    # The original value is preserved instead of silently discarding it.
    fecha_cita_original: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="pasaportes")


# ---------------------------------------------------------------------------
# canada
# ---------------------------------------------------------------------------


class Canada(RegistroBase):
    """Canadian visa or residency tramite (IRCC account)."""

    __tablename__ = "canada"
    __table_args__ = (
        Index("ix_canada_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("canada"),
        indice_trigramas("canada"),
    )

    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cuenta_ircc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="canada")


# ---------------------------------------------------------------------------
# usuarios — system operators and administrators
# ---------------------------------------------------------------------------


class Rol(enum.StrEnum):
    """
    System roles.

    Only two, because the real team is two figures: whoever handles tramites
    and whoever administers. Adding more roles without a concrete need
    produces a permissions matrix nobody maintains.
    """

    #: Manages users, browses the audit log, and purges records.
    ADMIN = "admin"
    #: Operates day-to-day tramites, including looking up credentials.
    OPERADOR = "operador"


class Usuario(Base, TimestampMixin):
    """
    Person who accesses the system.

    Replaces the pair of environment variables `API_USERNAME` / `API_PASSWORD`
    previously used to authenticate a single shared administrator. With one
    user per person, the audit log can say *who* looked up a client's
    credential, which is exactly the point of auditing it.
    """

    __tablename__ = "usuarios"
    __table_args__ = (UniqueConstraint("correo_electronico", name="uq_usuarios_correo"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Uniqueness is declared as a named constraint in `__table_args__`, not
    # with `unique=True` here: that way the name matches the migration's, and
    # CI's drift detection doesn't read it as different.
    # It also has no `index=True`, because the constraint itself creates its index.
    correo_electronico: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    #: bcrypt hash. The column is named this way, not "contrasena", so the
    #: schema makes explicit that there's never plain text here.
    contrasena_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[Rol] = mapped_column(
        SAEnum(Rol, name="rol_usuario", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Rol.OPERADOR,
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_acceso_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def es_admin(self) -> bool:
        return self.rol is Rol.ADMIN


# ---------------------------------------------------------------------------
# logs_auditoria — trail of access to sensitive data
# ---------------------------------------------------------------------------


class NivelAuditoria(enum.StrEnum):
    """Severity of the event, to allow filtering the audit log."""

    INFO = "INFO"
    ADVERTENCIA = "ADVERTENCIA"
    ALERTA = "ALERTA"


class LogAuditoria(Base):
    """
    Immutable log of sensitive events.

    Exists because of the domain: the system stores credentials for real
    clients' government accounts. Decrypting one of them is the most
    delicate operation in the API, and without this record nobody could
    answer who looked it up, when, or for which client.

    The table deliberately has no soft delete or update: a log that can be
    edited isn't a log. Retention is applied by purging by age, never by
    correcting entries.
    """

    __tablename__ = "logs_auditoria"
    __table_args__ = (
        Index("ix_logs_auditoria_recurso", "recurso", "registro_id"),
        Index("ix_logs_auditoria_usuario_fecha", "usuario_id", "ocurrido_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
    #: Kept even if the user is deleted: an entry with no author is useless.
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    usuario_correo: Mapped[str | None] = mapped_column(Text, nullable=True)
    accion: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    recurso: Mapped[str | None] = mapped_column(Text, nullable=True)
    registro_id: Mapped[int | None] = mapped_column(nullable=True)
    cliente_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    nivel: Mapped[NivelAuditoria] = mapped_column(
        SAEnum(
            NivelAuditoria,
            name="nivel_auditoria",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=NivelAuditoria.INFO,
    )
    direccion_ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    agente_usuario: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Extra context for the event. Never contains credentials: what's
    #: recorded is *what was looked up*, never *what was obtained*.
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
