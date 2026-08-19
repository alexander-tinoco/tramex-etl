"""
Tramex ETL pipeline: from the operational Excel file to the database.

Processes only the `Master Tramex`, `Global entry`, `Pasaportes` and `Canada`
sheets. The rest of the file (account numbers that aren't credentials, backup
codes, vacation sheets) is deliberately ignored.

Pipeline properties:

* **Idempotent.** Every row has a natural key derived from its identifying
  fields; the load uses `INSERT ... ON CONFLICT DO UPDATE`, so reprocessing
  the same file never duplicates anything.
* **Transactional.** The four sheets go in as a single transaction: if
  anything fails, the database is left as it was.
* **No pointless rewrites.** A row whose content hasn't changed isn't
  touched, which also avoids re-encrypting credentials that are unchanged.
* **Secure.** Credentials are encrypted with Fernet before being persisted
  and are never printed, not even in debug mode.

Usage:

    export DATABASE_URL="postgresql+psycopg2://user:password@host:5432/tramex"
    export TRAMEX_FERNET_KEY="<generated with generate_key.py>"

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
    """Defines the pipeline's command-line interface."""
    parser = argparse.ArgumentParser(
        prog="etl_tramex",
        description="Loads the Tramex operational file into the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("archivo", type=Path, help="Path to the source .xlsx file.")
    parser.add_argument(
        "--modo",
        choices=("upsert", "reemplazar"),
        default="upsert",
        help=(
            "upsert (default) reconciles the file with what already exists. "
            "reemplazar archives everything currently active before loading, to "
            "rebuild the state from scratch."
        ),
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=1000,
        help="How many rows are written per statement (default 1000).",
    )
    parser.add_argument(
        "--solo",
        nargs="+",
        choices=tuple(HOJAS_POR_TABLA),
        metavar="TABLA",
        help="Processes only the sheets given instead of all four.",
    )
    parser.add_argument(
        "--simulacion",
        action="store_true",
        help=(
            "Runs the full load and rolls back the transaction at the end. "
            "Reports exactly what would change, without changing anything."
        ),
    )
    parser.add_argument(
        "--nivel-log",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Output verbosity.",
    )
    return parser


def imprimir_resumen(resumen: ResumenCarga) -> None:
    """Writes the run's result in a format that's legible at a glance."""
    encabezado = "DRY RUN (nothing was written)" if resumen.simulacion else "LOAD COMPLETE"
    ancho = 66
    print()
    print("=" * ancho)
    print(f" {encabezado}")
    print("=" * ancho)
    print(f" {'table':<18}{'new':>10}{'updated':>15}{'unchanged':>15}")
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
    print(f" Duration: {resumen.duracion_segundos} s")
    if not resumen.hubo_cambios:
        print(" No changes: the file was already reconciled with the database.")
    print("=" * ancho)
    print()


def ejecutar(argumentos: argparse.Namespace) -> ResumenCarga:
    """Orchestrates the pipeline's three phases."""
    cargar_dotenv()
    configurar_logging(argumentos.nivel_log)

    url = obtener_url_base_de_datos()
    fernet = obtener_fernet()

    logger.info("Reading %s", argumentos.archivo)
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
    """Entry point. Returns the process exit code."""
    argumentos = construir_parser().parse_args(argv)
    try:
        resumen = ejecutar(argumentos)
    except (ErrorDeConfiguracion, ErrorDeEstructura, ErrorDeCarga) as exc:
        # Expected, actionable errors: reported without dumping a traceback
        # that tells the pipeline operator nothing useful.
        logger.error("%s", exc)
        return 1
    except Exception:
        logger.exception("The pipeline failed unexpectedly; nothing was written")
        return 2

    imprimir_resumen(resumen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
