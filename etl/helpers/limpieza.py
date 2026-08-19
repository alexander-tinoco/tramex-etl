"""
Pure cell-cleaning functions.

Deliberately isolated from pandas, the database, and the filesystem: this is
the logic with the most edge cases in the whole pipeline (the source file is
a spreadsheet maintained by hand for years) and it needs to be testable
without setting anything up.

Every function in this module takes a cell value and returns the normalized
value or `None`. None of them raise exceptions over dirty data: a bad value
gets dropped or preserved, but never stops a load of thousands of rows.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

logger = logging.getLogger("etl.limpieza")

#: Values the sheets use to mean "empty" besides a blank cell.
CENTINELAS_VACIOS = {"", "-", "--", "n/a", "na", "s/d", "sin dato", "nan", "none", "nat", "null"}

_SOLO_DIGITOS = re.compile(r"\D")

#: Deliberately loose validation: the goal isn't to certify the mailbox
#: exists, but to discard the free text the sheet accumulates in the email
#: column ("no tiene", "preguntar", "@example.com" with no local part).
_CORREO_PLAUSIBLE = re.compile(r"[^@\s]+@[^@\s]+\.[a-z]{2,}")
_ESPACIOS = re.compile(r"\s+")

#: Date formats observed in the source file, in order of frequency.
FORMATOS_DE_FECHA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%d.%m.%Y")


def _es_nulo(valor: Any) -> bool:
    """Detects nulls without depending on pandas, to keep the module pure."""
    if valor is None:
        return True
    # NaN is the only value that isn't equal to itself.
    return isinstance(valor, float) and valor != valor


def limpiar_texto(valor: Any) -> str | None:
    """
    Trims, collapses internal whitespace, and turns empty values into `None`.

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
    Keeps only the phone number's digits.

    No fixed length is assumed: the file mixes 10-digit local numbers,
    numbers with an international code, and extensions. Normalizing to a
    single format would destroy information the operator can actually
    interpret.

    >>> limpiar_telefono("(447) 114-8272")
    '4471148272'
    >>> limpiar_telefono("+52 55 1234 5678")
    '525512345678'
    >>> limpiar_telefono("sin telefono") is None
    True
    """
    if _es_nulo(valor):
        return None
    # Phone numbers read as a number arrive with a trailing float decimal ("4471148272.0").
    texto = str(valor)
    if texto.endswith(".0"):
        texto = texto[:-2]
    digitos = _SOLO_DIGITOS.sub("", texto)
    return digitos or None


def limpiar_correo(valor: Any) -> str | None:
    """
    Normalizes to lowercase and discards anything not shaped like an email.

    A warning is logged for every discard so the operator can fix the source
    file; silently losing an email would mean losing a client's only contact
    channel.

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

    # Some cells pile up several emails separated by a space or comma.
    # The first valid one is kept instead of discarding the whole cell.
    for candidato in re.split(r"[\s,;/]+", texto):
        if _CORREO_PLAUSIBLE.fullmatch(candidato):
            return candidato

    logger.warning("Discarded email with invalid format: %r", texto)
    return None


def limpiar_pasaporte(valor: Any) -> str | None:
    """
    Normalizes the passport number to uppercase with no separators.

    It's the domain's strongest identifier, the one identity resolution
    depends on, so "g33 961340" and "G33961340" should converge.

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
    Parses a date cell, returning `(date, original_text)`.

    Many cells carry free text instead of a date ("MARZO", "pendiente", "ya
    fue"). Discarding them would lose information the operator actually
    uses, so the text is preserved as-is in the tuple's second position.
    Only one of the two positions can hold a value.

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

    logger.info("Unrecognized date, preserved as text: %r", texto)
    return None, texto
