"""
Transformation: from a raw DataFrame to records ready to persist.

Every function in this module is pure: it takes a DataFrame and returns a
list of dictionaries. None of them touch the database, encrypt anything, or
depend on the environment, so the pipeline's business logic with the most
edge cases can be tested without any infrastructure.

Encryption happens later, at load time, on purpose: `hash_fila` must be
computed over the plaintext (Fernet produces a different ciphertext on every
call, so comparing those would always report a change).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pandas as pd

from etl.helpers.limpieza import (
    limpiar_correo,
    limpiar_pasaporte,
    limpiar_telefono,
    limpiar_texto,
    parsear_fecha,
)
from tramex_shared import ENTIDADES, calcular_clave_natural, calcular_hash_fila

logger = logging.getLogger("etl.transform")

#: Which cleaner to apply to each column. Columns not listed use `limpiar_texto`.
LIMPIADORES: dict[str, Callable[[Any], Any]] = {
    "telefono": limpiar_telefono,
    "correo_electronico": limpiar_correo,
    "numero_pasaporte": limpiar_pasaporte,
}


def limpiar_registro(fila: dict[str, Any]) -> dict[str, Any]:
    """
    Applies the matching cleaner to each field of a row.

    >>> limpiar_registro({"nombre": "  Ana  ", "telefono": "(447) 114-8272"})
    {'nombre': 'Ana', 'telefono': '4471148272'}
    """
    return {campo: LIMPIADORES.get(campo, limpiar_texto)(valor) for campo, valor in fila.items()}


def transformar(tabla: str, marco: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Converts a sheet's DataFrame into normalized, unique records.

    Returns each row with its `clave_natural` and `hash_fila` already
    computed. Rows with no name are discarded: in the source file those are
    visual separators and totals, not clients.

    When two rows from the same sheet produce the same natural key (for
    example, the same person captured twice with different spacing), the
    last one is kept, since it's the most recent version according to the
    file's order, and the discard is logged.
    """
    definicion = ENTIDADES[tabla]
    registros: dict[str, dict[str, Any]] = {}
    descartadas_sin_nombre = 0
    colapsadas = 0

    for cruda in marco.to_dict(orient="records"):
        fila = limpiar_registro(cruda)

        if fila.get("nombre") is None:
            descartadas_sin_nombre += 1
            continue

        # The Pasaportes sheet stores dates and free text in the same cell.
        if "fecha_cita_cruda" in fila:
            fecha, texto_original = parsear_fecha(cruda.get("fecha_cita_cruda"))
            fila.pop("fecha_cita_cruda")
            fila["fecha_cita"] = fecha
            fila["fecha_cita_original"] = texto_original

        clave = calcular_clave_natural(
            tabla, (fila.get(campo) for campo in definicion.campos_clave)
        )
        hash_fila = calcular_hash_fila(
            {campo: fila.get(campo) for campo in definicion.campos_negocio}
        )

        if clave in registros:
            colapsadas += 1

        registros[clave] = {**fila, "clave_natural": clave, "hash_fila": hash_fila}

    if descartadas_sin_nombre:
        logger.info(
            "%s: %d row(s) with no name discarded (separators or totals in the file)",
            tabla,
            descartadas_sin_nombre,
        )
    if colapsadas:
        logger.warning(
            "%s: %d duplicate row(s) within the file collapsed by natural key",
            tabla,
            colapsadas,
        )

    logger.info("%s: %d record(s) ready", tabla, len(registros))
    return list(registros.values())


def proyectar_clientes(
    registros_por_tabla: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Extracts the person data present in the tramite records.

    Returns one projection per tramite row, without deduplicating: resolving
    which projections belong to the same person requires querying the
    database, and therefore lives in the load layer, not here.
    """
    campos = ENTIDADES["clientes"].campos_negocio
    return [
        {campo: registro.get(campo) for campo in campos}
        for registros in registros_por_tabla.values()
        for registro in registros
    ]
