"""
Modelos ORM de SQLAlchemy.

El modelo relacional gira alrededor de la entidad `Cliente`: una persona que
contrata a la agencia puede tener simultaneamente un tramite de pasaporte, uno
de Global Entry y uno de Canada. En la hoja de calculo original esa relacion
era implicita (el mismo nombre repetido en cuatro pestanas distintas); aqui es
explicita mediante claves foraneas.

Convenciones transversales a todas las tablas de tramite:

- `clave_natural`  Huella estable de los campos que identifican al registro en
                   el archivo de origen. Es UNIQUE y permite que el ETL sea
                   idempotente mediante `INSERT ... ON CONFLICT DO UPDATE`.
- `hash_fila`      Huella de *todos* los campos de negocio en texto plano. Si
                   no cambia entre dos corridas del ETL, la fila se deja
                   intacta (evita reescrituras y re-cifrados innecesarios).
- `eliminado_en`   Borrado logico. Los datos personales nunca se destruyen de
                   inmediato: se marcan y se purgan segun la politica de
                   retencion documentada en docs/decisions/0005.
"""

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    """Marcas de tiempo y borrado logico compartidas por todas las tablas."""

    cargado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    eliminado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class IngestaMixin:
    """Columnas que hacen reproducible e idempotente la carga desde el ETL."""

    clave_natural: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    hash_fila: Mapped[str] = mapped_column(Text, nullable=False)


def indice_clave_natural(tabla: str) -> Index:
    """
    Indice unico *parcial* sobre la clave natural de los registros activos.

    La unicidad se restringe a `eliminado_en IS NULL` a proposito. Un UNIQUE
    total impediria conservar el historial: la carga original, que hacia
    `INSERT` ciego, dejo filas duplicadas en la base, y al archivarlas seguirian
    ocupando su clave e impedirian volver a insertar la version buena. Con el
    indice parcial pueden coexistir un registro activo y cualquier cantidad de
    versiones archivadas de la misma identidad.
    """
    return Index(
        f"uq_{tabla}_clave_natural_activa",
        "clave_natural",
        unique=True,
        postgresql_where=text("eliminado_en IS NULL"),
        sqlite_where=text("eliminado_en IS NULL"),
    )


# ---------------------------------------------------------------------------
# clientes — raiz del modelo relacional
# ---------------------------------------------------------------------------


class Cliente(Base, TimestampMixin, IngestaMixin):
    """Persona que contrata uno o mas tramites con la agencia."""

    __tablename__ = "clientes"
    __table_args__ = (indice_clave_natural("clientes"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)
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


class MasterTramex(Base, TimestampMixin, IngestaMixin):
    """Tramite principal (visa americana y afines)."""

    __tablename__ = "master_tramex"
    __table_args__ = (
        Index("ix_master_tramex_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("master_tramex"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)
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


class GlobalEntry(Base, TimestampMixin, IngestaMixin):
    """Tramite de Global Entry."""

    __tablename__ = "global_entry"
    __table_args__ = (
        Index("ix_global_entry_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("global_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    correo_electronico: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="global_entry")


# ---------------------------------------------------------------------------
# pasaportes
# ---------------------------------------------------------------------------


class Pasaporte(Base, TimestampMixin, IngestaMixin):
    """Tramite de expedicion o renovacion de pasaporte."""

    __tablename__ = "pasaportes"
    __table_args__ = (
        Index("ix_pasaportes_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("pasaportes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    apellido: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    lugar_cita: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_cita: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # El Excel de origen contiene celdas de fecha con texto libre ("MARZO").
    # Se preserva el valor original en vez de descartarlo silenciosamente.
    fecha_cita_original: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="pasaportes")


# ---------------------------------------------------------------------------
# canada
# ---------------------------------------------------------------------------


class Canada(Base, TimestampMixin, IngestaMixin):
    """Tramite de visa o residencia canadiense (cuenta IRCC)."""

    __tablename__ = "canada"
    __table_args__ = (
        Index("ix_canada_cliente_activo", "cliente_id", "eliminado_en"),
        indice_clave_natural("canada"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    cuenta_ircc: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    numero_pasaporte: Mapped[str | None] = mapped_column(Text, nullable=True)
    contrasena_cifrada: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship(back_populates="canada")


# ---------------------------------------------------------------------------
# usuarios — operadoras y administradores del sistema
# ---------------------------------------------------------------------------


class Rol(enum.StrEnum):
    """
    Roles del sistema.

    Solo dos, porque el equipo real son dos figuras: quien atiende tramites y
    quien administra. Anadir mas roles sin una necesidad concreta produce una
    matriz de permisos que nadie mantiene.
    """

    #: Gestiona usuarios, consulta la bitacora de auditoria y purga registros.
    ADMIN = "admin"
    #: Opera los tramites del dia a dia, incluida la consulta de credenciales.
    OPERADOR = "operador"


class Usuario(Base, TimestampMixin):
    """
    Persona que accede al sistema.

    Sustituye al par de variables de entorno `API_USERNAME` / `API_PASSWORD`
    con el que antes se autenticaba un unico administrador compartido. Con un
    usuario por persona, la bitacora de auditoria puede decir *quien* consulto
    la credencial de un cliente, que es justamente el punto de auditarla.
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    correo_electronico: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    #: Hash bcrypt. La columna se llama asi, y no "contrasena", para que quede
    #: explicito en el esquema que aqui nunca hay texto plano.
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
# logs_auditoria — rastro de acceso a datos sensibles
# ---------------------------------------------------------------------------


class NivelAuditoria(enum.StrEnum):
    """Severidad del evento, para poder filtrar la bitacora."""

    INFO = "INFO"
    ADVERTENCIA = "ADVERTENCIA"
    ALERTA = "ALERTA"


class LogAuditoria(Base):
    """
    Bitacora inmutable de eventos sensibles.

    Existe por el dominio: el sistema guarda credenciales de cuentas
    gubernamentales de clientes reales. Descifrar una de ellas es la operacion
    mas delicada de la API y, sin este registro, nadie podria responder quien
    la consulto, cuando ni de que cliente.

    La tabla no tiene borrado logico ni actualizacion a proposito: una bitacora
    que se puede editar no sirve como bitacora. La retencion se aplica
    purgando por antiguedad, nunca corrigiendo asientos.
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
    #: Se conserva aunque el usuario se elimine: un asiento sin autor no sirve.
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
    #: Contexto adicional del evento. Nunca contiene credenciales: lo que se
    #: registra es *que se consulto*, jamas *que se obtuvo*.
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
