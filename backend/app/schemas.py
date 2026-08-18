"""
Esquemas Pydantic v2 de entrada y salida de la API.

Convenciones:

- `*Create`   Campos aceptados al dar de alta un registro.
- `*Update`   Todos los campos opcionales; semantica PATCH.
- `*Response` Lo que la API devuelve. Nunca incluye `contrasena_cifrada` ni la
              contrasena en claro: para eso existe el endpoint auditado
              `GET /{id}/password`.

Las columnas de identidad (`clave_natural`, `hash_fila`) tampoco se exponen:
son un detalle de implementacion del pipeline de ingesta, no parte del contrato
publico.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Envuelve cualquier lista con metadatos de paginacion."""

    total: int = Field(description="Total de registros que cumplen el filtro.")
    skip: int = Field(description="Registros omitidos desde el inicio.")
    limit: int = Field(description="Tamano maximo de la pagina.")
    items: list[T]


class RegistroResponse(BaseModel):
    """Campos administrativos comunes a toda respuesta de registro."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cargado_en: datetime
    actualizado_en: datetime
    eliminado_en: datetime | None = Field(
        default=None,
        description="Marca de borrado logico. Nulo si el registro esta activo.",
    )


# ===========================================================================
# Clientes
# ===========================================================================


class ClienteBase(BaseModel):
    """Datos de la persona que contrata los tramites."""

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
    """Cliente con el conteo de tramites asociados por tipo."""

    tramites: dict[str, int] = Field(
        default_factory=dict,
        description="Cantidad de tramites activos por tabla.",
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
            "Cliente al que pertenece el tramite. Si se omite, se resuelve o se "
            "da de alta automaticamente a partir de los datos del registro."
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
        description="Se cifra con Fernet antes de persistirse; nunca se devuelve en las lecturas.",
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
            "Texto original de la celda cuando no era una fecha valida "
            '(el archivo de origen contiene valores como "MARZO").'
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
# Respuestas auxiliares
# ===========================================================================


class ContrasenaResponse(BaseModel):
    """Resultado del endpoint auditado de descifrado."""

    contrasena: str | None = Field(
        description="Contrasena en claro, o nulo si el registro no tiene ninguna."
    )
    registro_id: int
    recurso: str
