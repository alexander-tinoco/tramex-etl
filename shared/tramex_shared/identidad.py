"""
Reproducible record identity.

This module is the single source of truth for how a row's identity is
computed. Both the ETL pipeline (`etl/`) and the API (`backend/`) import it,
because both write to the same tables: if the ETL and the API derived the
key differently, a client entered by hand by an operator and the same client
present in the Excel file would end up as two separate records.

Two distinct fingerprints are computed, each with a different purpose:

`clave_natural`
    Fingerprint of the fields that *identify* the record (who it is). It's
    declared UNIQUE in the database and is the target of the upsert's
    `ON CONFLICT`, so reprocessing the same Excel file never duplicates rows.

`hash_fila`
    Fingerprint of *all* the business fields. It detects whether anything
    actually changed: if the hash matches the stored one, the upsert doesn't
    rewrite the row. This matters especially for passwords, because Fernet
    produces a different ciphertext on every call (it uses a random IV and a
    timestamp); comparing ciphertexts would always report "changed". That's
    why the hash is computed over the normalized plaintext and never over
    the ciphertext.

Neither fingerprint is reversible: both are hexadecimal SHA-256 digests. A
password's plaintext feeds the hash but can't be recovered from it.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

#: An unlikely separator within the data, so that concatenating fields is
#: injective: ("ab", "c") and ("a", "bc") must produce different keys.
_SEPARADOR = "\x1f"

_ESPACIOS = re.compile(r"\s+")


def normalizar_identificador(valor: Any) -> str:
    """
    Brings a value into a comparable canonical form.

    Strips accents, collapses internal whitespace, trims the ends, and
    lowercases, so that "  JOSÉ  Ramírez " and "jose ramirez" produce the
    same key. Null values are represented as an empty string.

    >>> normalizar_identificador("  JOSÉ  Ramírez ")
    'jose ramirez'
    >>> normalizar_identificador(None)
    ''
    """
    if valor is None:
        return ""
    texto = str(valor).strip()
    if not texto or texto.lower() in {"nan", "none", "nat"}:
        return ""
    # NFKD separates the base character from its diacritic; the diacritics
    # (category Mn) are then dropped so that "ó" and "o" match.
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return _ESPACIOS.sub(" ", sin_acentos).strip().lower()


def _digerir(entidad: str, valores: Iterable[Any]) -> str:
    """Concatenates normalized values under a namespace and digests them."""
    partes = [entidad, *(normalizar_identificador(v) for v in valores)]
    return hashlib.sha256(_SEPARADOR.join(partes).encode("utf-8")).hexdigest()


def calcular_clave_natural(entidad: str, valores: Iterable[Any]) -> str:
    """
    Stable fingerprint of a record's identifying fields.

    `entidad` acts as a namespace (e.g. `"clientes"` or `"master_tramex"`),
    so two different tables with the same identifying values don't
    conceptually collide.

    >>> a = calcular_clave_natural("clientes", ["Ana Lopez", "G123"])
    >>> b = calcular_clave_natural("clientes", ["  ana   lopez ", "g123"])
    >>> a == b
    True
    >>> a == calcular_clave_natural("pasaportes", ["Ana Lopez", "G123"])
    False
    """
    return _digerir(entidad, valores)


def calcular_hash_fila(datos: Mapping[str, Any], excluir: Iterable[str] = ()) -> str:
    """
    Fingerprint of a row's full content, in normalized plaintext.

    Keys are sorted so the hash doesn't depend on the dict's insertion
    order. Fields in `excluir` are skipped: used to leave out administrative
    columns (`id`, timestamps, ciphertexts) that change without the business
    data having changed.

    >>> calcular_hash_fila({"a": 1, "b": 2}) == calcular_hash_fila({"b": 2, "a": 1})
    True
    >>> calcular_hash_fila({"a": 1, "b": 2}) == calcular_hash_fila({"a": 1, "b": 3})
    False
    """
    omitidas = set(excluir)
    pares: list[str] = []
    for clave in sorted(datos):
        if clave in omitidas:
            continue
        pares.append(f"{clave}={normalizar_identificador(datos[clave])}")
    return hashlib.sha256(_SEPARADOR.join(pares).encode("utf-8")).hexdigest()


def nombre_canonico(nombre: Any, apellido: Any = None) -> str:
    """
    Joins first and last name into a form comparable across sheets.

    The source file isn't consistent: Master Tramex stores the full name in
    a single column ("José Ramírez") while Pasaportes and Global Entry split
    it into two ("Ana" / "Lopez"). Without unifying them, the same person
    would produce different keys depending on which sheet they came from.

    >>> nombre_canonico("José Ramírez")
    'jose ramirez'
    >>> nombre_canonico("Ana", "Lopez") == nombre_canonico("  ana lopez  ")
    True
    """
    partes = [normalizar_identificador(nombre), normalizar_identificador(apellido)]
    return _ESPACIOS.sub(" ", " ".join(p for p in partes if p)).strip()


def identificador_fuerte(datos: Mapping[str, Any]) -> str:
    """
    Returns a person's available hard identifier, or an empty string.

    The passport number is preferred because it's the domain's only truly
    unique value; email acts as a fallback. Returning empty isn't an error:
    some sheets (Pasaportes) capture neither.
    """
    for campo in ("numero_pasaporte", "correo_electronico"):
        valor = normalizar_identificador(datos.get(campo))
        if valor:
            return f"{campo}:{valor}"
    return ""


def calcular_clave_cliente(datos: Mapping[str, Any]) -> str:
    """
    Natural key of a person.

    Made up of the canonical name plus whatever hard identifier is
    available. A record with neither passport nor email produces a "weak"
    key (name only); resolving those cases against already-known people is
    the caller's responsibility, not this function's, which must remain
    pure.

    >>> a = calcular_clave_cliente({"nombre": "José Ramírez", "numero_pasaporte": "G111"})
    >>> b = calcular_clave_cliente(
    ...     {"nombre": "jose", "apellido": "ramirez", "numero_pasaporte": " g111 "}
    ... )
    >>> a == b
    True
    """
    return _digerir(
        "clientes",
        (
            nombre_canonico(datos.get("nombre"), datos.get("apellido")),
            identificador_fuerte(datos),
        ),
    )


def clave_es_debil(datos: Mapping[str, Any]) -> bool:
    """
    Indicates whether the person carries no hard identifier.

    Weak keys are ambiguous by construction: two namesakes with neither
    passport nor email are indistinguishable. Marking them lets them be
    handled with a different resolution strategy instead of blindly
    creating a new person.
    """
    return identificador_fuerte(datos) == ""
