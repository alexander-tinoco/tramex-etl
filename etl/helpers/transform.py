"""
Transformacion: de DataFrame crudo a registros listos para persistir.

Todas las funciones de este modulo son puras: reciben un DataFrame y devuelven
una lista de diccionarios. No tocan la base de datos, no cifran nada y no
dependen del entorno, de modo que la logica de negocio con mas casos raros del
pipeline se puede probar sin infraestructura.

El cifrado ocurre mas adelante, en la carga, y a proposito: `hash_fila` debe
calcularse sobre el texto plano (Fernet produce un criptograma distinto en cada
llamada, asi que compararlos siempre indicaria cambio).
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

#: Que limpiador aplicar a cada columna. Las no listadas usan `limpiar_texto`.
LIMPIADORES: dict[str, Callable[[Any], Any]] = {
    "telefono": limpiar_telefono,
    "correo_electronico": limpiar_correo,
    "numero_pasaporte": limpiar_pasaporte,
}


def limpiar_registro(fila: dict[str, Any]) -> dict[str, Any]:
    """
    Aplica el limpiador correspondiente a cada campo de una fila.

    >>> limpiar_registro({"nombre": "  Ana  ", "telefono": "(447) 114-8272"})
    {'nombre': 'Ana', 'telefono': '4471148272'}
    """
    return {campo: LIMPIADORES.get(campo, limpiar_texto)(valor) for campo, valor in fila.items()}


def transformar(tabla: str, marco: pd.DataFrame) -> list[dict[str, Any]]:
    """
    Convierte el DataFrame de una hoja en registros normalizados y unicos.

    Devuelve cada fila con su `clave_natural` y su `hash_fila` ya calculados.
    Las filas sin nombre se descartan: en el archivo de origen son separadores
    visuales y totales, no clientes.

    Cuando dos filas de la misma hoja producen la misma clave natural (por
    ejemplo la misma persona capturada dos veces con distinto espaciado) se
    conserva la ultima, que es la version mas reciente segun el orden del
    archivo, y se registra el descarte.
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

        # La hoja de Pasaportes guarda fechas y texto libre en la misma celda.
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
            "%s: %d fila(s) sin nombre descartadas (separadores o totales del archivo)",
            tabla,
            descartadas_sin_nombre,
        )
    if colapsadas:
        logger.warning(
            "%s: %d fila(s) duplicadas dentro del archivo colapsadas por clave natural",
            tabla,
            colapsadas,
        )

    logger.info("%s: %d registro(s) listos", tabla, len(registros))
    return list(registros.values())


def proyectar_clientes(
    registros_por_tabla: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """
    Extrae los datos de persona presentes en los registros de tramite.

    Devuelve una proyeccion por cada fila de tramite, sin deduplicar: la
    resolucion de que proyecciones corresponden a la misma persona necesita
    consultar la base y por lo tanto vive en la capa de carga, no aqui.
    """
    campos = ENTIDADES["clientes"].campos_negocio
    return [
        {campo: registro.get(campo) for campo in campos}
        for registros in registros_por_tabla.values()
        for registro in registros
    ]
