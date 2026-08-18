"""
Pipeline ETL de Tramex: del archivo Excel operativo a la base de datos.

Procesa unicamente las hojas `Master Tramex`, `Global entry`, `Pasaportes` y
`Canada`. El resto del archivo (numeros de cuenta que no son credenciales,
codigos de respaldo, hojas de vacaciones) se ignora deliberadamente.

Propiedades del pipeline:

* **Idempotente.** Cada fila tiene una clave natural derivada de sus campos
  identificadores; la carga usa `INSERT ... ON CONFLICT DO UPDATE`, de modo que
  reprocesar el mismo archivo no duplica nada.
* **Transaccional.** Las cuatro hojas entran en una sola transaccion: si algo
  falla, la base queda como estaba.
* **Sin reescrituras inutiles.** Una fila cuyo contenido no cambio no se toca,
  lo que ademas evita volver a cifrar credenciales intactas.
* **Seguro.** Las credenciales se cifran con Fernet antes de persistirse y
  nunca se imprimen, ni siquiera en modo depuracion.

Uso:

    export DATABASE_URL="postgresql+psycopg2://usuario:clave@host:5432/tramex"
    export TRAMEX_FERNET_KEY="<generada con generate_key.py>"

    python -m etl.etl_tramex raw-data/TRAMEX.xlsx
    python -m etl.etl_tramex raw-data/TRAMEX.xlsx --simulacion
    python -m etl.etl_tramex raw-data/TRAMEX.xlsx --modo reemplazar
    python -m etl.etl_tramex raw-data/TRAMEX.xlsx --solo pasaportes canada
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine

from etl.helpers.config import (
    ErrorDeConfiguracion,
    cargar_dotenv,
    configurar_logging,
    obtener_fernet,
    obtener_url_base_de_datos,
)
from etl.helpers.extract import HOJAS_POR_TABLA, ErrorDeEstructura, leer_archivo
from etl.helpers.load import ErrorDeCarga, ResumenCarga, cargar
from etl.helpers.transform import transformar

logger = logging.getLogger("etl")


def construir_parser() -> argparse.ArgumentParser:
    """Define la interfaz de linea de comandos del pipeline."""
    parser = argparse.ArgumentParser(
        prog="etl_tramex",
        description="Carga el archivo operativo de Tramex en la base de datos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("archivo", type=Path, help="Ruta al archivo .xlsx de origen.")
    parser.add_argument(
        "--modo",
        choices=("upsert", "reemplazar"),
        default="upsert",
        help=(
            "upsert (por omision) concilia el archivo con lo que ya existe. "
            "reemplazar archiva todo lo vigente antes de cargar, para reconstruir "
            "el estado desde cero."
        ),
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=1000,
        help="Cuantas filas se escriben por sentencia (por omision 1000).",
    )
    parser.add_argument(
        "--solo",
        nargs="+",
        choices=tuple(HOJAS_POR_TABLA),
        metavar="TABLA",
        help="Procesa solo las hojas indicadas en lugar de las cuatro.",
    )
    parser.add_argument(
        "--simulacion",
        action="store_true",
        help=(
            "Ejecuta la carga completa y revierte la transaccion al final. "
            "Informa exactamente que cambiaria, sin cambiar nada."
        ),
    )
    parser.add_argument(
        "--nivel-log",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Verbosidad de la salida.",
    )
    return parser


def imprimir_resumen(resumen: ResumenCarga) -> None:
    """Escribe el resultado de la corrida en un formato legible de un vistazo."""
    encabezado = "SIMULACION (no se escribio nada)" if resumen.simulacion else "CARGA COMPLETADA"
    ancho = 66
    print()
    print("=" * ancho)
    print(f" {encabezado}")
    print("=" * ancho)
    print(f" {'tabla':<18}{'nuevos':>10}{'actualizados':>15}{'sin cambios':>15}")
    print("-" * ancho)
    print(
        f" {'clientes':<18}{resumen.clientes.insertados:>10}"
        f"{resumen.clientes.actualizados:>15}{resumen.clientes.sin_cambios:>15}"
    )
    for tabla, detalle in resumen.por_tabla.items():
        print(
            f" {tabla:<18}{detalle.insertados:>10}"
            f"{detalle.actualizados:>15}{detalle.sin_cambios:>15}"
        )
    print("-" * ancho)
    print(f" Duracion: {resumen.duracion_segundos} s")
    if not resumen.hubo_cambios:
        print(" Sin novedades: el archivo ya estaba conciliado con la base.")
    print("=" * ancho)
    print()


def ejecutar(argumentos: argparse.Namespace) -> ResumenCarga:
    """Orquesta las tres fases del pipeline."""
    cargar_dotenv()
    configurar_logging(argumentos.nivel_log)

    url = obtener_url_base_de_datos()
    fernet = obtener_fernet()

    logger.info("Leyendo %s", argumentos.archivo)
    marcos = leer_archivo(argumentos.archivo, tuple(argumentos.solo) if argumentos.solo else None)

    registros = {tabla: transformar(tabla, marco) for tabla, marco in marcos.items()}

    engine = create_engine(url)
    try:
        return cargar(
            engine,
            registros,
            fernet=fernet,
            modo=argumentos.modo,
            tamano_lote=argumentos.lote,
            simulacion=argumentos.simulacion,
        )
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve el codigo de salida del proceso."""
    argumentos = construir_parser().parse_args(argv)
    try:
        resumen = ejecutar(argumentos)
    except (ErrorDeConfiguracion, ErrorDeEstructura, ErrorDeCarga) as exc:
        # Errores esperables y accionables: se informan sin volcar una traza
        # que no le dice nada a quien opera el pipeline.
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("El pipeline fallo de forma inesperada; no se escribio nada")
        return 2

    imprimir_resumen(resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
