"""
Identidad reproducible de registros.

Este modulo es la unica fuente de verdad sobre como se calcula la identidad de
una fila. Lo importan tanto el pipeline ETL (`etl/`) como la API (`backend/`),
porque ambos escriben en las mismas tablas: si el ETL y la API derivaran la
clave de forma distinta, un cliente dado de alta a mano por una operadora y el
mismo cliente presente en el Excel terminarian como dos registros separados.

Se calculan dos huellas distintas y con proposito distinto:

`clave_natural`
    Huella de los campos que *identifican* al registro (quien es). Se declara
    UNIQUE en la base de datos y es el objetivo del `ON CONFLICT` del upsert,
    de modo que reprocesar el mismo Excel no duplica filas.

`hash_fila`
    Huella de *todos* los campos de negocio. Permite detectar si algo cambio
    realmente: si el hash coincide con el almacenado, el upsert no reescribe la
    fila. Esto importa especialmente por las contrasenas, porque Fernet produce
    un criptograma distinto en cada llamada (usa IV aleatorio y marca de
    tiempo); comparar criptogramas siempre daria "cambio". Por eso el hash se
    calcula sobre el texto plano normalizado y nunca sobre el cifrado.

Ninguna de las dos huellas es reversible: son SHA-256 hexadecimales. El texto
plano de una contrasena entra al hash pero no se puede recuperar de el.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

#: Separador improbable dentro de los datos, para que la concatenacion de
#: campos sea inyectiva: ("ab", "c") y ("a", "bc") deben producir claves
#: distintas.
_SEPARADOR = "\x1f"

_ESPACIOS = re.compile(r"\s+")


def normalizar_identificador(valor: Any) -> str:
    """
    Lleva un valor a una forma canonica comparable.

    Quita acentos, colapsa espacios internos, recorta extremos y pasa a
    minusculas, de modo que "  JOSÉ  Ramírez " y "jose ramirez" produzcan la
    misma clave. Los valores nulos se representan como cadena vacia.

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
    # NFKD separa el caracter base de su diacritico; luego se descartan los
    # diacriticos (categoria Mn) para que "ó" y "o" coincidan.
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return _ESPACIOS.sub(" ", sin_acentos).strip().lower()


def _digerir(entidad: str, valores: Iterable[Any]) -> str:
    """Concatena valores normalizados bajo un espacio de nombres y los digiere."""
    partes = [entidad, *(normalizar_identificador(v) for v in valores)]
    return hashlib.sha256(_SEPARADOR.join(partes).encode("utf-8")).hexdigest()


def calcular_clave_natural(entidad: str, valores: Iterable[Any]) -> str:
    """
    Huella estable de los campos identificadores de un registro.

    `entidad` actua como espacio de nombres (por ejemplo `"clientes"` o
    `"master_tramex"`), de modo que dos tablas distintas con los mismos valores
    identificadores no colisionen conceptualmente.

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
    Huella del contenido completo de una fila, en texto plano y normalizado.

    Las claves se ordenan para que el hash no dependa del orden de insercion
    del diccionario. Los campos en `excluir` se omiten: se usa para dejar fuera
    columnas administrativas (`id`, marcas de tiempo, criptogramas) que cambian
    sin que el dato de negocio haya cambiado.

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
    Une nombre y apellido en una forma comparable entre hojas.

    El archivo de origen no es consistente: Master Tramex guarda el nombre
    completo en una sola columna ("José Ramírez") mientras que Pasaportes y
    Global Entry lo parten en dos ("Ana" / "Lopez"). Sin unificarlos, la misma
    persona produciria claves distintas segun la pestana de la que viniera.

    >>> nombre_canonico("José Ramírez")
    'jose ramirez'
    >>> nombre_canonico("Ana", "Lopez") == nombre_canonico("  ana lopez  ")
    True
    """
    partes = [normalizar_identificador(nombre), normalizar_identificador(apellido)]
    return _ESPACIOS.sub(" ", " ".join(p for p in partes if p)).strip()


def identificador_fuerte(datos: Mapping[str, Any]) -> str:
    """
    Devuelve el identificador duro disponible de una persona, o cadena vacia.

    Se prefiere el numero de pasaporte porque es el unico dato realmente
    univoco del dominio; el correo actua como respaldo. Que devuelva vacio no
    es un error: hay hojas (Pasaportes) que no capturan ninguno de los dos.
    """
    for campo in ("numero_pasaporte", "correo_electronico"):
        valor = normalizar_identificador(datos.get(campo))
        if valor:
            return f"{campo}:{valor}"
    return ""


def calcular_clave_cliente(datos: Mapping[str, Any]) -> str:
    """
    Clave natural de una persona.

    Se compone del nombre canonico mas el identificador duro disponible. Un
    registro sin pasaporte ni correo produce una clave "debil" (solo nombre);
    resolver esos casos contra las personas ya conocidas es responsabilidad de
    quien consulta, no de esta funcion, que debe seguir siendo pura.

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
    Indica si la persona no trae ningun identificador duro.

    Las claves debiles son ambiguas por construccion: dos homonimos sin
    pasaporte ni correo son indistinguibles. Marcarlas permite tratarlas con
    una estrategia de resolucion distinta en vez de crear una persona nueva a
    ciegas.
    """
    return identificador_fuerte(datos) == ""
