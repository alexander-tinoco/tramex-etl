"""
Extraccion: lectura de las hojas del archivo de origen.

La unica responsabilidad de este modulo es entregar un DataFrame con las
columnas esperadas ya renombradas. No limpia ni valida contenido; de eso se
encarga `transform`. Separarlo permite que la transformacion se pruebe con
DataFrames construidos a mano, sin necesidad de un Excel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger("etl.extract")


class ErrorDeEstructura(Exception):
    """El archivo de origen no tiene la forma que el pipeline espera."""


@dataclass(frozen=True)
class HojaOrigen:
    """
    Describe donde vive cada hoja y como se llaman sus columnas.

    `fila_encabezado` existe porque las hojas no son homogeneas: la principal
    arrastra cuatro filas de titulos y logotipos antes del encabezado real. El
    mapa de columnas conserva los nombres tal cual aparecen en el archivo,
    espacios finales incluidos, porque asi es como llegan.
    """

    nombre_hoja: str
    tabla_destino: str
    fila_encabezado: int
    columnas: dict[str, str]


#: Configuracion de las cuatro hojas que el pipeline procesa. El resto del
#: archivo (numeros de cuenta que no son credenciales, codigos de respaldo,
#: hojas de vacaciones) se ignora deliberadamente.
HOJAS = (
    HojaOrigen(
        nombre_hoja="Master Tramex",
        tabla_destino="master_tramex",
        # El encabezado real vive en la quinta fila de la hoja.
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
            # En la practica esta columna guarda la contrasena de la cuenta,
            # no un numero de cuenta. Se trata como credencial y se cifra.
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
            # Igual que en Global entry: "Cuenta Cita" es la credencial.
            "Cuenta Cita": "contrasena",
        },
    ),
)

HOJAS_POR_TABLA = {hoja.tabla_destino: hoja for hoja in HOJAS}


def _normalizar_encabezados(columnas: pd.Index) -> dict[str, str]:
    """
    Empareja los encabezados reales con los esperados de forma tolerante.

    Los nombres del archivo llevan espacios sobrantes y acentos inconsistentes
    que cambian entre revisiones de la hoja. Comparar por una forma reducida
    evita que el pipeline se rompa porque alguien borro un espacio final.
    """
    return {str(columna).strip().lower(): columna for columna in columnas}


def leer_hoja(ruta_excel: str | Path, hoja: HojaOrigen) -> pd.DataFrame:
    """
    Lee una hoja y devuelve un DataFrame con las columnas ya renombradas.

    Lanza `ErrorDeEstructura` si falta alguna columna esperada: es preferible
    detener la carga a insertar miles de filas con un campo silenciosamente
    vacio porque alguien renombro una columna.
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
            f"La hoja '{hoja.nombre_hoja}' no tiene las columnas {faltantes}. "
            f"Encabezados encontrados: {list(marco.columns)}"
        )

    marco = marco.rename(columns=renombres)[list(hoja.columnas.values())]
    logger.info("Hoja '%s': %d fila(s) leidas", hoja.nombre_hoja, len(marco))
    return marco


def leer_archivo(
    ruta_excel: str | Path, tablas: tuple[str, ...] | None = None
) -> dict[str, pd.DataFrame]:
    """Lee todas las hojas configuradas (o el subconjunto indicado)."""
    ruta = Path(ruta_excel)
    if not ruta.is_file():
        raise ErrorDeEstructura(f"No existe el archivo de origen: {ruta}")

    seleccion = HOJAS if tablas is None else tuple(HOJAS_POR_TABLA[t] for t in tablas)
    return {hoja.tabla_destino: leer_hoja(ruta, hoja) for hoja in seleccion}
