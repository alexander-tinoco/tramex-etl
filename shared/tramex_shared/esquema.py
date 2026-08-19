"""
Declarative definition of the business entities.

The ETL and the API share these definitions to derive `clave_natural` and
`hash_fila` the same way. Each entity declares:

`campos_clave`
    Columns that identify the record. Changing this list changes every
    existing natural key, so it amounts to a data migration.

`campos_negocio`
    Columns whose content represents the actual data. They feed `hash_fila`.

`campo_secreto`
    Name of the plaintext field that must be encrypted before persisting
    (or `None` if the entity doesn't handle credentials). It participates
    in `hash_fila` in plaintext but is never stored unencrypted.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DefinicionEntidad:
    """Identity and content rules for a business table."""

    tabla: str
    campos_clave: tuple[str, ...]
    campos_negocio: tuple[str, ...]
    campo_secreto: str | None = None
    #: Administrative columns that never participate in the content hash.
    campos_ignorados: tuple[str, ...] = field(
        default=(
            "id",
            "cliente_id",
            "clave_natural",
            "hash_fila",
            "cargado_en",
            "actualizado_en",
            "eliminado_en",
            "contrasena_cifrada",
        )
    )


CLIENTES = DefinicionEntidad(
    tabla="clientes",
    # A person is identified by their full name plus the first hard
    # identifier available. The passport is the strong identifier; email
    # acts as a fallback when the Excel file had no passport number.
    campos_clave=("nombre", "apellido", "numero_pasaporte", "correo_electronico"),
    campos_negocio=(
        "nombre",
        "apellido",
        "correo_electronico",
        "telefono",
        "numero_pasaporte",
    ),
)

MASTER_TRAMEX = DefinicionEntidad(
    tabla="master_tramex",
    campos_clave=("nombre", "numero_pasaporte", "id_solicitud"),
    campos_negocio=(
        "nombre",
        "id_solicitud",
        "telefono",
        "numero_pasaporte",
        "tramite",
        "cita",
        "correo_electronico",
        "contrasena",
    ),
    campo_secreto="contrasena",
)

GLOBAL_ENTRY = DefinicionEntidad(
    tabla="global_entry",
    campos_clave=("nombre", "apellido", "numero_pasaporte"),
    campos_negocio=(
        "nombre",
        "apellido",
        "correo_electronico",
        "numero_pasaporte",
        "contrasena",
    ),
    campo_secreto="contrasena",
)

PASAPORTES = DefinicionEntidad(
    tabla="pasaportes",
    campos_clave=("nombre", "apellido", "fecha_cita", "fecha_cita_original", "lugar_cita"),
    campos_negocio=(
        "nombre",
        "apellido",
        "telefono",
        "lugar_cita",
        "fecha_cita",
        "fecha_cita_original",
    ),
)

CANADA = DefinicionEntidad(
    tabla="canada",
    campos_clave=("nombre", "numero_pasaporte", "cuenta_ircc"),
    campos_negocio=(
        "nombre",
        "cuenta_ircc",
        "telefono",
        "numero_pasaporte",
        "contrasena",
    ),
    campo_secreto="contrasena",
)

#: Index by table name, to resolve the definition at runtime.
ENTIDADES: dict[str, DefinicionEntidad] = {
    definicion.tabla: definicion
    for definicion in (CLIENTES, MASTER_TRAMEX, GLOBAL_ENTRY, PASAPORTES, CANADA)
}
