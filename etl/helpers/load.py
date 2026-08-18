"""
Carga idempotente y transaccional.

Este modulo resuelve el defecto mas grave que tenia el pipeline: la version
anterior hacia `to_sql(..., if_exists="append")`, de modo que reprocesar el
mismo archivo duplicaba toda la base, y cargaba hoja por hoja sin transaccion,
de modo que un fallo en la tercera hoja dejaba las dos primeras a medias.

Ahora:

* Toda la carga ocurre dentro de **una sola transaccion**. Si algo falla, la
  base queda exactamente como estaba.
* Cada fila se escribe con `INSERT ... ON CONFLICT (clave_natural) DO UPDATE`,
  apuntando al indice unico parcial de registros activos. Reprocesar el mismo
  archivo no duplica nada.
* El `DO UPDATE` solo se aplica si `hash_fila` cambio, asi que una corrida sin
  novedades no reescribe filas ni vuelve a cifrar credenciales.

El esquema no se define aqui: lo posee Alembic (en el backend) y este modulo lo
**refleja**. Duplicar las definiciones de tabla seria una segunda fuente de
verdad que tarde o temprano divergiria.
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

#: Columnas que nunca se sobrescriben en un `DO UPDATE`: la identidad no cambia
#: (es la condicion del conflicto) y la fecha de alta debe conservarse.
COLUMNAS_INMUTABLES = frozenset({"id", "clave_natural", "cargado_en"})


class ErrorDeCarga(Exception):
    """La carga no pudo completarse; la transaccion se revierte entera."""


@dataclass
class ResumenTabla:
    """Conteo del efecto de la carga sobre una tabla."""

    insertados: int = 0
    actualizados: int = 0
    sin_cambios: int = 0

    @property
    def total(self) -> int:
        return self.insertados + self.actualizados + self.sin_cambios

    def __str__(self) -> str:
        return (
            f"{self.insertados} nuevo(s), {self.actualizados} actualizado(s), "
            f"{self.sin_cambios} sin cambios"
        )


@dataclass
class ResumenCarga:
    """Resultado completo de una corrida del pipeline."""

    por_tabla: dict[str, ResumenTabla] = field(default_factory=dict)
    clientes: ResumenTabla = field(default_factory=ResumenTabla)
    duracion_segundos: float = 0.0
    simulacion: bool = False

    @property
    def hubo_cambios(self) -> bool:
        resumenes = [self.clientes, *self.por_tabla.values()]
        return any(r.insertados or r.actualizados for r in resumenes)


def _en_lotes(secuencia: list[dict[str, Any]], tamano: int) -> Iterator[list[dict[str, Any]]]:
    """Parte una lista en lotes, para no armar sentencias de tamano ilimitado."""
    for inicio in range(0, len(secuencia), tamano):
        yield secuencia[inicio : inicio + tamano]


def reflejar_tablas(engine: Engine) -> dict[str, Table]:
    """
    Carga las definiciones de tabla desde la base viva.

    Si falta alguna, es senal de que las migraciones no se han aplicado; se
    prefiere un error explicito a una carga que fallaria a la mitad.
    """
    metadatos = MetaData()
    esperadas = ("clientes", *TABLAS_TRAMITE)
    try:
        metadatos.reflect(bind=engine, only=esperadas)
    except Exception as exc:
        raise ErrorDeCarga(
            "No se pudo leer el esquema de la base de datos. Aplica las migraciones "
            "antes de cargar: `cd backend && alembic upgrade head`."
        ) from exc

    faltantes = [nombre for nombre in esperadas if nombre not in metadatos.tables]
    if faltantes:
        raise ErrorDeCarga(f"Faltan tablas en la base de datos: {faltantes}.")
    return {nombre: metadatos.tables[nombre] for nombre in esperadas}


def _constructor_de_insert(conexion: Connection):
    """Elige el `INSERT` con soporte de `ON CONFLICT` del dialecto activo."""
    dialecto = conexion.dialect.name
    if dialecto == "postgresql":
        return insert_postgresql
    if dialecto == "sqlite":
        return insert_sqlite
    raise ErrorDeCarga(
        f"El dialecto '{dialecto}' no soporta upsert por clave natural. "
        "El pipeline requiere PostgreSQL (produccion) o SQLite (pruebas)."
    )


def _clasificar(
    conexion: Connection, tabla: Table, registros: list[dict[str, Any]]
) -> tuple[int, int, int]:
    """
    Cuenta cuantos registros son nuevos, cuantos cambian y cuantos no.

    Se consulta el estado previo antes de escribir porque ni PostgreSQL ni
    SQLite distinguen de forma portable un INSERT de un UPDATE en el resultado
    de un upsert, y un resumen honesto de la corrida es justamente lo que
    permite confiar en que reprocesar el archivo no altero nada.
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
    """Escribe los registros con upsert por clave natural, en lotes."""
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
        # Reprocesar el archivo debe poder reactivar un registro archivado sin
        # dejar dos copias vivas de la misma identidad.
        actualizables["eliminado_en"] = None
        actualizables["actualizado_en"] = text("CURRENT_TIMESTAMP")

        conexion.execute(
            sentencia.on_conflict_do_update(
                index_elements=["clave_natural"],
                index_where=text("eliminado_en IS NULL"),
                set_=actualizables,
                # Sin cambios reales no se toca la fila: evita reescrituras
                # masivas y, sobre todo, volver a cifrar credenciales intactas.
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
    Da de alta a las personas y devuelve el mapa `clave_cliente -> id`.

    Aplica la misma estrategia de dos pasadas que la API: primero las
    proyecciones con identificador duro (pasaporte o correo), que son las que
    definen quien es quien, y despues las que no lo tienen, que se enganchan
    por nombre canonico solo si apuntan a una unica persona conocida. Ante un
    nombre ambiguo se crea una persona nueva: unir despues dos expedientes que
    quedaron sueltos es trivial, separar dos que se fusionaron por error no.

    El mapa devuelto incluye tambien las claves debiles resueltas por alias, de
    modo que quien llama pueda buscar por la clave del registro sin saber como
    se resolvio.
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
    #: Claves debiles que apuntan a la clave de otra persona ya conocida.
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

    # Los alias se resuelven al final, cuando las personas nuevas ya tienen id.
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
    Persiste los registros transformados dentro de una unica transaccion.

    `modo="reemplazar"` archiva todo lo que hay antes de cargar, para
    reconstruir el estado desde cero a partir del archivo. `simulacion=True`
    ejecuta la carga completa y revierte al final: sirve para saber exactamente
    que cambiaria una corrida sin llegar a cambiarlo.
    """
    if modo not in {"upsert", "reemplazar"}:
        raise ErrorDeCarga(f"Modo de carga desconocido: {modo!r}.")

    tablas = reflejar_tablas(engine)
    resumen = ResumenCarga(simulacion=simulacion)
    inicio = time.perf_counter()

    # `engine.begin()` abre una transaccion unica: o entra todo el archivo, o
    # no entra nada. La version anterior cargaba hoja por hoja y podia dejar la
    # base a medias.
    with engine.begin() as conexion:
        if modo == "reemplazar":
            for nombre in TABLAS_TRAMITE:
                conexion.execute(
                    tablas[nombre]
                    .update()
                    .where(tablas[nombre].c.eliminado_en.is_(None))
                    .values(eliminado_en=text("CURRENT_TIMESTAMP"))
                )
            logger.info("Modo reemplazar: registros vigentes archivados antes de la carga")

        proyecciones = [
            {campo: registro.get(campo) for campo in ENTIDADES["clientes"].campos_negocio}
            for registros in registros_por_tabla.values()
            for registro in registros
        ]
        clientes_por_clave, resumen.clientes = _resolver_clientes(
            conexion, tablas["clientes"], proyecciones, tamano_lote
        )
        logger.info("Clientes: %s", resumen.clientes)

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
            # Se revierte todo: la simulacion debe poder ejecutarse contra la
            # base real sin dejar rastro.
            conexion.rollback()
            logger.warning("Simulacion: la transaccion se revirtio, nada se escribio")

    resumen.duracion_segundos = round(time.perf_counter() - inicio, 3)
    return resumen
