"""
Funciones puras de limpieza de celdas.

Estan aisladas de pandas, de la base de datos y del sistema de archivos a
proposito: son la logica con mas casos raros de todo el pipeline (el archivo de
origen es una hoja de calculo mantenida a mano durante anos) y necesitan ser
testeables sin montar nada.

Toda funcion de este modulo recibe un valor de celda y devuelve el valor
normalizado o `None`. Ninguna lanza excepciones por datos sucios: un dato malo
se descarta o se preserva, pero nunca detiene una carga de miles de filas.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("etl.limpieza")

#: Valores que las hojas usan como "vacio" ademas de la celda en blanco.
CENTINELAS_VACIOS = {"", "-", "--", "n/a", "na", "s/d", "sin dato", "nan", "none", "nat", "null"}

_SOLO_DIGITOS = re.compile(r"\D")

#: Validacion deliberadamente laxa: el objetivo no es certificar que el buzon
#: exista, sino descartar el texto libre que la hoja acumula en la columna de
#: correo ("no tiene", "preguntar", "@example.com" sin parte local).
_CORREO_PLAUSIBLE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
_ESPACIOS = re.compile(r"\s+")

#: Formatos de fecha observados en el archivo de origen, en orden de frecuencia.
FORMATOS_DE_FECHA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%d.%m.%Y")


def _es_nulo(valor: Any) -> bool:
    """Detecta nulos sin depender de pandas, para que el modulo sea puro."""
    if valor is None:
        return True
    # NaN es el unico valor que no es igual a si mismo.
    return isinstance(valor, float) and valor != valor


def limpiar_texto(valor: Any) -> str | None:
    """
    Recorta, colapsa espacios internos y convierte los vacios en `None`.

    >>> limpiar_texto("  Jorge   Monroy ")
    'Jorge Monroy'
    >>> limpiar_texto("   ") is None
    True
    >>> limpiar_texto("N/A") is None
    True
    """
    if _es_nulo(valor):
        return None
    texto = _ESPACIOS.sub(" ", str(valor)).strip()
    if texto.lower() in CENTINELAS_VACIOS:
        return None
    return texto or None


def limpiar_telefono(valor: Any) -> str | None:
    """
    Deja solo los digitos del telefono.

    No se asume una longitud fija: el archivo mezcla numeros locales de 10
    digitos, numeros con lada internacional y extensiones. Normalizar a un
    formato unico destruiria informacion que la operadora si sabe interpretar.

    >>> limpiar_telefono("(447) 114-8272")
    '4471148272'
    >>> limpiar_telefono("+52 55 1234 5678")
    '525512345678'
    >>> limpiar_telefono("sin telefono") is None
    True
    """
    if _es_nulo(valor):
        return None
    # Los telefonos leidos como numero llegan con decimal flotante ("4471148272.0").
    texto = str(valor)
    if texto.endswith(".0"):
        texto = texto[:-2]
    digitos = _SOLO_DIGITOS.sub("", texto)
    return digitos or None


def limpiar_correo(valor: Any) -> str | None:
    """
    Normaliza a minusculas y descarta lo que no tiene forma de correo.

    Se registra una advertencia por cada descarte para que el operador pueda
    corregir el archivo de origen; perder un correo en silencio significaria
    perder el unico canal de contacto de un cliente.

    >>> limpiar_correo("  Jorge@Example.COM ")
    'jorge@example.com'
    >>> limpiar_correo("no tiene correo") is None
    True
    >>> limpiar_correo("dos@correos.com otro@correo.com")
    'dos@correos.com'
    """
    if _es_nulo(valor):
        return None
    texto = str(valor).strip().lower()
    if not texto or texto in CENTINELAS_VACIOS:
        return None

    # Algunas celdas acumulan varios correos separados por espacio o coma.
    # Se conserva el primero que sea valido en vez de descartar la celda entera.
    for candidato in re.split(r"[\s,;/]+", texto):
        if _CORREO_PLAUSIBLE.fullmatch(candidato):
            return candidato

    logger.warning("Correo con formato invalido descartado: %r", texto)
    return None


def limpiar_pasaporte(valor: Any) -> str | None:
    """
    Normaliza el numero de pasaporte a mayusculas sin separadores.

    Es el identificador mas fuerte del dominio, del que depende la resolucion
    de identidad, asi que conviene que "g33 961340" y "G33961340" converjan.

    >>> limpiar_pasaporte("g33 961340")
    'G33961340'
    >>> limpiar_pasaporte("G-111")
    'G111'
    """
    texto = limpiar_texto(valor)
    if texto is None:
        return None
    normalizado = re.sub(r"[\s\-_/.]", "", texto).upper()
    return normalizado or None


def parsear_fecha(valor: Any) -> tuple[date | None, str | None]:
    """
    Interpreta una celda de fecha devolviendo `(fecha, texto_original)`.

    Muchas celdas traen texto libre en lugar de una fecha ("MARZO", "pendiente",
    "ya fue"). Descartarlas perderia informacion que la operadora si usa, asi
    que se preserva el texto tal cual en la segunda posicion de la tupla. Solo
    una de las dos posiciones puede tener valor.

    >>> parsear_fecha("15/08/2026")
    (datetime.date(2026, 8, 15), None)
    >>> parsear_fecha("MARZO")
    (None, 'MARZO')
    >>> parsear_fecha(None)
    (None, None)
    """
    if _es_nulo(valor):
        return None, None
    if isinstance(valor, datetime):
        return valor.date(), None
    if isinstance(valor, date):
        return valor, None

    texto = limpiar_texto(valor)
    if texto is None:
        return None, None

    for formato in FORMATOS_DE_FECHA:
        try:
            return datetime.strptime(texto, formato).date(), None
        except ValueError:
            continue

    logger.info("Fecha no reconocida, se preserva como texto: %r", texto)
    return None, texto
