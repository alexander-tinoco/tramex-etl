"""
Idempotent, transactional load.

This module fixes the most serious flaw the pipeline had: the previous
version did `to_sql(..., if_exists="append")`, so reprocessing the same file
duplicated the entire database, and it loaded sheet by sheet with no
transaction, so a failure on the third sheet left the first two half-loaded.

Now:

* The whole load happens inside **a single transaction**. If anything fails,
  the database is left exactly as it was.
* Every row is written with `INSERT ... ON CONFLICT (clave_natural) DO
  UPDATE`, targeting the partial unique index over active records.
  Reprocessing the same file never duplicates anything.
* The `DO UPDATE` only applies if `hash_fila` changed, so a run with no
  changes doesn't rewrite rows or re-encrypt credentials.

The schema isn't defined here: Alembic (in the backend) owns it, and this
module **mirrors** it. Duplicating the table definitions would be a second
source of truth that would eventually drift out of sync.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.dialects.postgresql import insert as insert_postgresql
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from sqlalchemy.engine import Connection, Engine

from tramex_shared import (
    ENTIDADES,
    calcular_clave_cliente,
    calcular_hash_fila,
    clave_es_debil,
    nombre_canonico,
)

logger = logging.getLogger("etl.load")

TABLAS_TRAMITE = ("master_tramex", "global_entry", "pasaportes", "canada")

#: Columns that are never overwritten in a `DO UPDATE`: identity doesn't
#: change (it's the conflict condition) and the creation date must be kept.
COLUMNAS_INMUTABLES = frozenset({"id", "clave_natural", "cargado_en"})


class ErrorDeCarga(Exception):
    """The load couldn't complete; the whole transaction is rolled back."""


@dataclass
class ResumenTabla:
    """Count of the load's effect on a table."""

    insertados: int = 0
    actualizados: int = 0
    sin_cambios: int = 0

    @property
    def total(self) -> int:
        return self.insertados + self.actualizados + self.sin_cambios

    def __str__(self) -> str:
        return f"{self.insertados} new, {self.actualizados} updated, {self.sin_cambios} unchanged"


@dataclass
class ResumenCarga:
    """Full result of a pipeline run."""

    por_tabla: dict[str, ResumenTabla] = field(default_factory=dict)
    clientes: ResumenTabla = field(default_factory=ResumenTabla)
    duracion_segundos: float = 0.0
    simulacion: bool = False

    @property
    def hubo_cambios(self) -> bool:
        resumenes = [self.clientes, *self.por_tabla.values()]
        return any(r.insertados or r.actualizados for r in resumenes)


def _en_lotes(secuencia: list[dict[str, Any]], tamano: int) -> Iterator[list[dict[str, Any]]]:
    """Splits a list into batches, to avoid building statements of unbounded size."""
    for inicio in range(0, len(secuencia), tamano):
        yield secuencia[inicio : inicio + tamano]


def reflejar_tablas(engine: Engine) -> dict[str, Table]:
    """
    Loads the table definitions from the live database.

    If any is missing, it's a sign the migrations haven't been applied; an
    explicit error is preferable to a load that would fail halfway through.
    """
    metadatos = MetaData()
    esperadas = ("clientes", *TABLAS_TRAMITE)
    try:
        metadatos.reflect(bind=engine, only=esperadas)
    except Exception as exc:
        raise ErrorDeCarga(
            "Could not read the database schema. Apply the migrations before "
            "loading: `cd backend && alembic upgrade head`."
        ) from exc

    faltantes = [nombre for nombre in esperadas if nombre not in metadatos.tables]
    if faltantes:
        raise ErrorDeCarga(f"Missing tables in the database: {faltantes}.")
    return {nombre: metadatos.tables[nombre] for nombre in esperadas}


def _constructor_de_insert(conexion: Connection):
    """Picks the `INSERT` with `ON CONFLICT` support for the active dialect."""
    dialecto = conexion.dialect.name
    if dialecto == "postgresql":
        return insert_postgresql
    if dialecto == "sqlite":
        return insert_sqlite
    raise ErrorDeCarga(
        f"Dialect '{dialecto}' does not support upsert by natural key. "
        "The pipeline requires PostgreSQL (production) or SQLite (tests)."
    )


def _clasificar(
    conexion: Connection, tabla: Table, registros: list[dict[str, Any]]
) -> tuple[int, int, int]:
    """
    Counts how many records are new, how many change, and how many don't.

    The previous state is queried before writing because neither PostgreSQL
    nor SQLite portably distinguish an INSERT from an UPDATE in an upsert's
    result, and an honest summary of the run is exactly what lets you trust
    that reprocessing the file changed nothing.
    """
    claves = [registro["clave_natural"] for registro in registros]
    filas = conexion.execute(
        select(tabla.c.clave_natural, tabla.c.hash_fila).where(
            tabla.c.clave_natural.in_(claves), tabla.c.eliminado_en.is_(None)
        )
    ).all()
    previos: dict[str, str] = {fila[0]: fila[1] for fila in filas}

    nuevos = actualizados = iguales = 0
    for registro in registros:
        anterior = previos.get(registro["clave_natural"])
        if anterior is None:
            nuevos += 1
        elif anterior != registro["hash_fila"]:
            actualizados += 1
        else:
            iguales += 1
    return nuevos, actualizados, iguales


def _upsert(
    conexion: Connection, tabla: Table, registros: list[dict[str, Any]], tamano_lote: int
) -> ResumenTabla:
    """Writes the records with upsert by natural key, in batches."""
    resumen = ResumenTabla()
    if not registros:
        return resumen

    constructor = _constructor_de_insert(conexion)
    columnas_tabla = set(tabla.c.keys())

    for lote in _en_lotes(registros, tamano_lote):
        nuevos, actualizados, iguales = _clasificar(conexion, tabla, lote)
        resumen.insertados += nuevos
        resumen.actualizados += actualizados
        resumen.sin_cambios += iguales

        valores = [
            {campo: valor for campo, valor in registro.items() if campo in columnas_tabla}
            for registro in lote
        ]

        sentencia = constructor(tabla).values(valores)
        actualizables = {
            columna: sentencia.excluded[columna]
            for columna in valores[0]
            if columna not in COLUMNAS_INMUTABLES
        }
        # Reprocessing the file must be able to reactivate an archived record
        # without leaving two live copies of the same identity.
        actualizables["eliminado_en"] = None
        actualizables["actualizado_en"] = text("CURRENT_TIMESTAMP")

        conexion.execute(
            sentencia.on_conflict_do_update(
                index_elements=["clave_natural"],
                index_where=text("eliminado_en IS NULL"),
                set_=actualizables,
                # With no real changes, the row isn't touched: this avoids
                # mass rewrites and, above all, re-encrypting unchanged
                # credentials.
                where=tabla.c.hash_fila != sentencia.excluded.hash_fila,
            )
        )

    return resumen


def _resolver_clientes(
    conexion: Connection,
    tabla_clientes: Table,
    proyecciones: Iterable[dict[str, Any]],
    tamano_lote: int,
) -> tuple[dict[str, int], ResumenTabla]:
    """
    Registers the people and returns the `clave_cliente -> id` map.

    Applies the same two-pass strategy as the API: first the projections
    with a hard identifier (passport or email), which are the ones that
    define who's who, and then the ones without one, which are attached by
    canonical name only if they point to a single known person. An ambiguous
    name creates a new person instead: merging two records that were left
    separate later is trivial, splitting two that were merged by mistake is
    not.

    The returned map also includes the weak keys resolved by alias, so the
    caller can look up by a record's key without knowing how it was resolved.
    """
    existentes = conexion.execute(
        select(
            tabla_clientes.c.id,
            tabla_clientes.c.nombre,
            tabla_clientes.c.apellido,
            tabla_clientes.c.clave_natural,
        ).where(tabla_clientes.c.eliminado_en.is_(None))
    ).all()

    ids_por_clave: dict[str, int] = {fila.clave_natural: fila.id for fila in existentes}
    claves_por_nombre: dict[str, set[str]] = {}
    for fila in existentes:
        claves_por_nombre.setdefault(nombre_canonico(fila.nombre, fila.apellido), set()).add(
            fila.clave_natural
        )

    campos = ENTIDADES["clientes"].campos_negocio
    nuevos: dict[str, dict[str, Any]] = {}
    #: Weak keys that point to the key of another already-known person.
    alias: dict[str, str] = {}

    for debiles in (False, True):
        for proyeccion in proyecciones:
            if clave_es_debil(proyeccion) is not debiles:
                continue

            clave = calcular_clave_cliente(proyeccion)
            if clave in ids_por_clave or clave in nuevos or clave in alias:
                continue

            canonico = nombre_canonico(proyeccion.get("nombre"), proyeccion.get("apellido"))

            if debiles:
                candidatos = claves_por_nombre.get(canonico, set())
                if len(candidatos) == 1:
                    alias[clave] = next(iter(candidatos))
                    continue

            nuevos[clave] = {
                **{campo: proyeccion.get(campo) for campo in campos},
                "clave_natural": clave,
                "hash_fila": calcular_hash_fila({campo: proyeccion.get(campo) for campo in campos}),
            }
            claves_por_nombre.setdefault(canonico, set()).add(clave)

    resumen = _upsert(conexion, tabla_clientes, list(nuevos.values()), tamano_lote)

    if nuevos:
        recien = conexion.execute(
            select(tabla_clientes.c.clave_natural, tabla_clientes.c.id).where(
                tabla_clientes.c.clave_natural.in_(list(nuevos))
            )
        ).all()
        ids_por_clave.update({fila.clave_natural: fila.id for fila in recien})

    # Aliases are resolved last, once the new people already have an id.
    for clave_debil, destino in alias.items():
        ids_por_clave[clave_debil] = ids_por_clave[destino]

    return ids_por_clave, resumen


def cargar(
    engine: Engine,
    registros_por_tabla: dict[str, list[dict[str, Any]]],
    *,
    fernet: Fernet,
    modo: str = "upsert",
    tamano_lote: int = 1000,
    simulacion: bool = False,
) -> ResumenCarga:
    """
    Persists the transformed records inside a single transaction.

    `modo="reemplazar"` archives everything that exists before loading, to
    rebuild the state from scratch from the file. `simulacion=True` runs the
    full load and rolls back at the end: it's for finding out exactly what a
    run would change without actually changing it.
    """
    if modo not in {"upsert", "reemplazar"}:
        raise ErrorDeCarga(f"Unknown load mode: {modo!r}.")

    tablas = reflejar_tablas(engine)
    resumen = ResumenCarga(simulacion=simulacion)
    inicio = time.perf_counter()

    # `engine.begin()` opens a single transaction: either the whole file goes
    # in, or none of it does. The previous version loaded sheet by sheet and
    # could leave the database half-loaded.
    with engine.begin() as conexion:
        if modo == "reemplazar":
            for nombre in TABLAS_TRAMITE:
                conexion.execute(
                    tablas[nombre]
                    .update()
                    .where(tablas[nombre].c.eliminado_en.is_(None))
                    .values(eliminado_en=text("CURRENT_TIMESTAMP"))
                )
            logger.info("Replace mode: active records archived before loading")

        proyecciones = [
            {campo: registro.get(campo) for campo in ENTIDADES["clientes"].campos_negocio}
            for registros in registros_por_tabla.values()
            for registro in registros
        ]
        clientes_por_clave, resumen.clientes = _resolver_clientes(
            conexion, tablas["clientes"], proyecciones, tamano_lote
        )
        logger.info("Clients: %s", resumen.clientes)

        for nombre, registros in registros_por_tabla.items():
            definicion = ENTIDADES[nombre]
            preparados: list[dict[str, Any]] = []

            for registro in registros:
                fila = dict(registro)
                fila["cliente_id"] = clientes_por_clave[calcular_clave_cliente(fila)]

                if definicion.campo_secreto:
                    secreto = fila.pop(definicion.campo_secreto, None)
                    fila["contrasena_cifrada"] = (
                        fernet.encrypt(str(secreto).encode()).decode() if secreto else None
                    )
                preparados.append(fila)

            resumen.por_tabla[nombre] = _upsert(conexion, tablas[nombre], preparados, tamano_lote)
            logger.info("%s: %s", nombre, resumen.por_tabla[nombre])

        if simulacion:
            # Everything is rolled back: the dry run must be able to execute
            # against the real database without leaving a trace.
            conexion.rollback()
            logger.warning("Dry run: the transaction was rolled back, nothing was written")

    resumen.duracion_segundos = round(time.perf_counter() - inicio, 3)
    return resumen
