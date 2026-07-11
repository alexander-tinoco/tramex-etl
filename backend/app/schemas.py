"""
Esquemas Pydantic v2 para validación de entrada/salida de la API.

Convenciones:
- *Base: campos para creación (sin id ni cargado_en).
- *Update: todos los campos opcionales para PATCH.
- *Response: incluye id y cargado_en; excluye contrasena_cifrada por seguridad.
"""

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Respuesta paginada genérica
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel, Generic[T]):
    """Envuelve cualquier lista con metadatos de paginación."""
    total: int
    skip: int
    limit: int
    items: list[T]


# ===========================================================================
# MasterTramex
# ===========================================================================

class MasterTramexBase(BaseModel):
    """Esquema de creación para master_tramex."""
    nombre: str
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: EmailStr | None = None
    contrasena: str | None = None  # Se cifra en el router antes de guardar


class MasterTramexUpdate(BaseModel):
    """Esquema de actualización parcial para master_tramex."""
    nombre: str | None = None
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: EmailStr | None = None
    contrasena: str | None = None


class MasterTramexResponse(BaseModel):
    """Esquema de respuesta para master_tramex (sin contraseña)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    id_solicitud: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    tramite: str | None = None
    cita: str | None = None
    correo_electronico: str | None = None
    cargado_en: datetime


# ===========================================================================
# GlobalEntry
# ===========================================================================

class GlobalEntryBase(BaseModel):
    """Esquema de creación para global_entry."""
    nombre: str
    apellido: str | None = None
    correo_electronico: EmailStr | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class GlobalEntryUpdate(BaseModel):
    """Esquema de actualización parcial para global_entry."""
    nombre: str | None = None
    apellido: str | None = None
    correo_electronico: EmailStr | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class GlobalEntryResponse(BaseModel):
    """Esquema de respuesta para global_entry (sin contraseña)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str | None = None
    correo_electronico: str | None = None
    numero_pasaporte: str | None = None
    cargado_en: datetime


# ===========================================================================
# Pasaportes
# ===========================================================================

class PasaporteBase(BaseModel):
    """Esquema de creación para pasaportes."""
    nombre: str
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = None


class PasaporteUpdate(BaseModel):
    """Esquema de actualización parcial para pasaportes."""
    nombre: str | None = None
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = None


class PasaporteResponse(BaseModel):
    """Esquema de respuesta para pasaportes."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str | None = None
    telefono: str | None = None
    lugar_cita: str | None = None
    fecha_cita: date | None = None
    fecha_cita_original: str | None = None
    cargado_en: datetime


# ===========================================================================
# Canada
# ===========================================================================

class CanadaBase(BaseModel):
    """Esquema de creación para canada."""
    nombre: str
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class CanadaUpdate(BaseModel):
    """Esquema de actualización parcial para canada."""
    nombre: str | None = None
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    contrasena: str | None = None


class CanadaResponse(BaseModel):
    """Esquema de respuesta para canada (sin contraseña)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    cuenta_ircc: str | None = None
    telefono: str | None = None
    numero_pasaporte: str | None = None
    cargado_en: datetime
