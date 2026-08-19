"""
Pydantic v2 input and output schemas for the API.

Conventions:

- `*Create`   Fields accepted when creating a record.
- `*Update`   All fields optional; PATCH semantics.
- `*Response` What the API returns. Never includes `contrasena_cifrada` nor
              the plain-text password: that's what the audited
              `GET /{id}/password` endpoint is for.

The identity columns (`clave_natural`, `hash_fila`) aren't exposed either:
they're an implementation detail of the ingestion pipeline, not part of the
public contract.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")

#: Roles are declared as a literal so they appear in the OpenAPI schema as a
#: readable enum, instead of as a free-form string.
RolUsuario = Literal["admin", "operador"]


class PaginatedResponse(BaseModel, Generic[T]):
    """Wraps any list with pagination metadata."""

    total: int = Field(description="Total records matching the filter.")
    skip: int = Field(description="Records skipped from the start.")
    limit: int = Field(description="Maximum page size.")
    items: list[T]


class RegistroResponse(BaseModel):
    """Administrative fields common to every record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cargado_en: datetime
    actualizado_en: datetime
    eliminado_en: datetime | None = Field(
        default=None,
        description="Soft-delete timestamp. Null if the record is active.",
    )


# ===========================================================================
# Clientes
# ===========================================================================


class ClienteBase(BaseModel):
    """Data of the person contracting the tramites."""

    nombre: str = Field(min_length=1, max_length=200, examples=["Jorge Monroy"])
    apellido: str | None = Field(default=None, max_length=200)
    correo_electronico: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=30)
    numero_pasaporte: str | None = Field(default=None, max_length=30)


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    apellido: str | None = None
    correo_electronico: EmailStr | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None


class ClienteResponse(ClienteBase, RegistroResponse):
    correo_electronico: str | None = None


class ClienteDetalleResponse(ClienteResponse):
    """Client with the count of associated tramites by type."""

    tramites: dict[str, int] = Field(
        default_factory=dict,
        description="Number of active tramites per table.",
        examples=[{"master_tramex": 1, "global_entry": 0, "pasaportes": 2, "canada": 0}],
    )


# ===========================================================================
# Master Tramex
# ===========================================================================


class MasterTramexBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    cliente_id: int | None = Field(
        default=None,
        description=(
            "Client the tramite belongs to. If omitted, it's resolved or "
            "created automatically from the record's data."
        ),
    )
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: EmailStr | None = None
    contrasena: str | None = Field(
        default=None,
        description="Encrypted with Fernet before being persisted; never returned on reads.",
    )


class MasterTramexUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    cliente_id: int | None = None
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: EmailStr | None = None
    contrasena: str | None = None


class MasterTramexResponse(RegistroResponse):
    cliente_id: int
    nombre: str
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: str | None = None


# ===========================================================================
# Global Entry
# ===========================================================================


class GlobalEntryBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    cliente_id: int | None = None
    apellido: str | None = None
    correo_electronico: EmailStr | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class GlobalEntryUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    cliente_id: int | None = None
    apellido: str | None = None
    correo_electronico: EmailStr | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class GlobalEntryResponse(RegistroResponse):
    cliente_id: int
    nombre: str
    apellido: str | None = None
    correo_electronico: str | None = None
    numero_pasaporte: str | None = None


# ===========================================================================
# Pasaportes
# ===========================================================================


class PasaporteBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    cliente_id: int | None = None
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = Field(
        default=None,
        description=(
            "Original text of the cell when it wasn't a valid date "
            '(the source file contains values like "MARZO").'
        ),
    )


class PasaporteUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    cliente_id: int | None = None
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = None


class PasaporteResponse(RegistroResponse):
    cliente_id: int
    nombre: str
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = None


# ===========================================================================
# Canada
# ===========================================================================


class CanadaBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    cliente_id: int | None = None
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class CanadaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    cliente_id: int | None = None
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class CanadaResponse(RegistroResponse):
    cliente_id: int
    nombre: str
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None


# ===========================================================================
# Auxiliary responses
# ===========================================================================


class ContrasenaResponse(BaseModel):
    """Result of the audited decryption endpoint."""

    contrasena: str | None = Field(
        description="Plain-text password, or null if the record has none."
    )
    registro_id: int
    recurso: str
    auditoria_id: int = Field(
        description=(
            "Identifier of the log entry this lookup left in the audit log. "
            "Every read of a credential is recorded."
        )
    )


# ===========================================================================
# Authentication and users
# ===========================================================================


class TokenResponse(BaseModel):
    """
    Login response.

    The token is also returned in the body, in addition to the `httpOnly`
    cookie, because Swagger, scripts, and integrations don't use cookies.
    The dashboard ignores this field and relies solely on the cookie.
    """

    access_token: str
    token_type: str = "bearer"
    expira_en_minutos: int
    usuario: UsuarioResponse


class UsuarioBase(BaseModel):
    correo_electronico: EmailStr
    nombre: str = Field(min_length=1, max_length=200)


class UsuarioCreate(UsuarioBase):
    contrasena: str = Field(
        min_length=12,
        max_length=128,
        description=(
            "At least 12 characters. The system holds third-party government "
            "account credentials, so the account that unlocks them can't be "
            "protected with a short password."
        ),
    )
    rol: RolUsuario = Field(default="operador")


class UsuarioUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    rol: RolUsuario | None = None
    activo: bool | None = None


class CambioContrasena(BaseModel):
    contrasena_actual: str
    contrasena_nueva: str = Field(min_length=12, max_length=128)


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correo_electronico: str
    nombre: str
    rol: RolUsuario
    activo: bool
    ultimo_acceso_en: datetime | None = None
    cargado_en: datetime


class LogAuditoriaResponse(BaseModel):
    """Audit log entry. Never contains credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ocurrido_en: datetime
    usuario_id: int | None = None
    usuario_correo: str | None = None
    accion: str
    recurso: str | None = None
    registro_id: int | None = None
    cliente_id: int | None = None
    nivel: str
    direccion_ip: str | None = None
    detalle: str | None = None


class ResultadoRetencion(BaseModel):
    """Summary of a retention policy run."""

    dias_retencion: int
    purgados_por_tabla: dict[str, int]
    asientos_de_auditoria_purgados: int
    total_purgado: int


TokenResponse.model_rebuild()
