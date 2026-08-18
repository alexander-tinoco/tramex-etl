"""
Definicion declarativa de las entidades de negocio.

El ETL y la API comparten estas definiciones para derivar `clave_natural` y
`hash_fila` de la misma forma. Cada entidad declara:

`campos_clave`
    Columnas que identifican al registro. Cambiar esta lista cambia todas las
    claves naturales existentes, asi que constituye una migracion de datos.

`campos_negocio`
    Columnas cuyo contenido representa el dato real. Alimentan `hash_fila`.

`campo_secreto`
    Nombre del campo en texto plano que debe cifrarse antes de persistirse
    (o `None` si la entidad no maneja credenciales). Participa en `hash_fila`
    en claro pero jamas se almacena sin cifrar.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DefinicionEntidad:
    """Reglas de identidad y de contenido de una tabla de negocio."""

    tabla: str
    campos_clave: tuple[str, ...]
    campos_negocio: tuple[str, ...]
    campo_secreto: str | None = None
    #: Columnas administrativas que nunca participan del hash de contenido.
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
    # Una persona se identifica por su nombre completo mas el primer dato duro
    # disponible. El pasaporte es el identificador fuerte; el correo actua como
    # respaldo cuando el Excel no traia numero de pasaporte.
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

#: Indice por nombre de tabla, para resolver la definicion en tiempo de ejecucion.
ENTIDADES: dict[str, DefinicionEntidad] = {
    definicion.tabla: definicion
    for definicion in (CLIENTES, MASTER_TRAMEX, GLOBAL_ENTRY, PASAPORTES, CANADA)
}
