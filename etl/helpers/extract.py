"""
Extraction: reading the sheets from the source file.

This module's only responsibility is to hand back a DataFrame with the
expected columns already renamed. It doesn't clean or validate content;
that's `transform`'s job. Separating them lets the transformation be tested
with hand-built DataFrames, without needing an Excel file.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger("etl.extract")


class ErrorDeEstructura(Exception):
    """The source file doesn't have the shape the pipeline expects."""


@dataclass(frozen=True)
class HojaOrigen:
    """
    Describes where each sheet lives and what its columns are called.

    `fila_encabezado` exists because the sheets aren't uniform: the main one
    carries four rows of titles and logos before the real header. The column
    map keeps the names exactly as they appear in the file, trailing spaces
    included, because that's how they arrive.
    """

    nombre_hoja: str
    tabla_destino: str
    fila_encabezado: int
    columnas: dict[str, str]


#: Configuration for the four sheets the pipeline processes. The rest of the
#: file (account numbers that aren't credentials, backup codes, vacation
#: sheets) is deliberately ignored.
HOJAS = (
    HojaOrigen(
        nombre_hoja="Master Tramex",
        tabla_destino="master_tramex",
        # The real header lives on the sheet's fifth row.
        fila_encabezado=4,
        columnas={
            "NOMBRE": "nombre",
            "ID ": "id_solicitud",
            "Telefono": "telefono",
            "N°Pasaporte ": "numero_pasaporte",
            "TRAMITE": "tramite",
            "CITA ": "cita",
            "Correo electrónico": "correo_electronico",
            "CONTRASEÑA": "contrasena",
        },
    ),
    HojaOrigen(
        nombre_hoja="Global entry",
        tabla_destino="global_entry",
        fila_encabezado=0,
        columnas={
            "Nombre": "nombre",
            "Apellido ": "apellido",
            "Correo electrónico": "correo_electronico",
            "Número de pasaporte": "numero_pasaporte",
            # In practice this column holds the account password, not an
            # account number. It's treated as a credential and encrypted.
            "Número de la cuenta": "contrasena",
        },
    ),
    HojaOrigen(
        nombre_hoja="Pasaportes",
        tabla_destino="pasaportes",
        fila_encabezado=0,
        columnas={
            "Nombre": "nombre",
            "Apellido ": "apellido",
            "Teléfono": "telefono",
            "Lugar de la cita": "lugar_cita",
            "Fecha Cita": "fecha_cita_cruda",
        },
    ),
    HojaOrigen(
        nombre_hoja="Canada",
        tabla_destino="canada",
        fila_encabezado=0,
        columnas={
            "NOMBRE": "nombre",
            "Cuenta IRCC": "cuenta_ircc",
            "Telefono": "telefono",
            "N°Pasaporte ": "numero_pasaporte",
            # Same as in Global entry: "Cuenta Cita" is the credential.
            "Cuenta Cita": "contrasena",
        },
    ),
)

HOJAS_POR_TABLA = {hoja.tabla_destino: hoja for hoja in HOJAS}


def _normalizar_encabezados(columnas: pd.Index) -> dict[str, str]:
    """
    Matches the real headers to the expected ones tolerantly.

    The names in the file carry extra spaces and inconsistent accents that
    change between revisions of the sheet. Comparing by a reduced form keeps
    the pipeline from breaking because someone removed a trailing space.
    """
    return {str(columna).strip().lower(): columna for columna in columnas}


def leer_hoja(ruta_excel: str | Path, hoja: HojaOrigen) -> pd.DataFrame:
    """
    Reads a sheet and returns a DataFrame with the columns already renamed.

    Raises `ErrorDeEstructura` if any expected column is missing: it's better
    to stop the load than to insert thousands of rows with a silently empty
    field because someone renamed a column.
    """
    marco = pd.read_excel(ruta_excel, sheet_name=hoja.nombre_hoja, header=hoja.fila_encabezado)
    disponibles = _normalizar_encabezados(marco.columns)

    renombres: dict[str, str] = {}
    faltantes: list[str] = []
    for esperada, destino in hoja.columnas.items():
        real = disponibles.get(esperada.strip().lower())
        if real is None:
            faltantes.append(esperada)
        else:
            renombres[real] = destino

    if faltantes:
        raise ErrorDeEstructura(
            f"Sheet '{hoja.nombre_hoja}' is missing columns {faltantes}. "
            f"Headers found: {list(marco.columns)}"
        )

    marco = marco.rename(columns=renombres)[list(hoja.columnas.values())]
    logger.info("Sheet '%s': %d row(s) read", hoja.nombre_hoja, len(marco))
    return marco


def leer_archivo(
    ruta_excel: str | Path, tablas: tuple[str, ...] | None = None
) -> dict[str, pd.DataFrame]:
    """Reads all configured sheets (or the given subset)."""
    ruta = Path(ruta_excel)
    if not ruta.is_file():
        raise ErrorDeEstructura(f"Source file does not exist: {ruta}")

    seleccion = HOJAS if tablas is None else tuple(HOJAS_POR_TABLA[t] for t in tablas)
    return {hoja.tabla_destino: leer_hoja(ruta, hoja) for hoja in seleccion}
