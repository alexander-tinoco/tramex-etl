#!/usr/bin/env python3
"""
End-to-end verification of the ETL pipeline in continuous integration.

The ETL's unit tests run against SQLite with hand-built DataFrames. This
script checks what those can't: that the full pipeline works against real
PostgreSQL, reading an actual Excel file, and that reprocessing it **doesn't
duplicate anything** — the property that motivated its rewrite in the first
place.

The data is synthetic. The real file contains personal client information and
must never enter the repository or a runner.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parents[2]

FILAS_MASTER = 120
FILAS_GLOBAL = 40
FILAS_PASAPORTES = 60
FILAS_CANADA = 30
#: Expected distinct people: all sheets describe the same set of people.
CLIENTES_ESPERADOS = FILAS_MASTER


def construir_excel(destino: Path) -> None:
    """Generates a workbook with the structure and quirks of the real file."""
    master = pd.DataFrame(
        {
            "NOMBRE": [f"Persona Sintetica {i:03d}" for i in range(1, FILAS_MASTER + 1)],
            "ID ": [f"SOL{i:05d}" for i in range(1, FILAS_MASTER + 1)],
            "Telefono": [f"(44{i % 10}) 11{i:03d}-{i:04d}" for i in range(1, FILAS_MASTER + 1)],
            "N°Pasaporte ": [f"G{i:06d}" for i in range(1, FILAS_MASTER + 1)],
            "TRAMITE": ["VISA B1/B2"] * FILAS_MASTER,
            "CITA ": ["Pendiente"] * FILAS_MASTER,
            "Correo electrónico": [f"persona{i:03d}@example.com" for i in range(1, FILAS_MASTER + 1)],
            "CONTRASEÑA": [f"clave-{i:03d}" for i in range(1, FILAS_MASTER + 1)],
        }
    )
    # Real quirks of the file: nameless filler rows and a duplicate capture
    # of the same person with different spacing and capitalization.
    master.loc[len(master)] = [None] * 8
    master.loc[len(master)] = ["  persona   sintetica 001 ", "SOL00001", "(440) 11001-0001",
                               "g000001", "VISA B1/B2", "Pendiente",
                               "persona001@example.com", "clave-001"]

    global_entry = pd.DataFrame(
        {
            "Nombre": ["Persona"] * FILAS_GLOBAL,
            "Apellido ": [f"Sintetica {i:03d}" for i in range(1, FILAS_GLOBAL + 1)],
            "Correo electrónico": [f"persona{i:03d}@example.com" for i in range(1, FILAS_GLOBAL + 1)],
            "Número de pasaporte": [f"G{i:06d}" for i in range(1, FILAS_GLOBAL + 1)],
            "Número de la cuenta": [f"ge-{i:03d}" for i in range(1, FILAS_GLOBAL + 1)],
        }
    )

    pasaportes = pd.DataFrame(
        {
            "Nombre": ["Persona"] * FILAS_PASAPORTES,
            "Apellido ": [f"Sintetica {i:03d}" for i in range(1, FILAS_PASAPORTES + 1)],
            "Teléfono": [f"55{i:08d}" for i in range(1, FILAS_PASAPORTES + 1)],
            "Lugar de la cita": ["CDMX"] * FILAS_PASAPORTES,
            # Mix of valid dates and free text, like the real file.
            "Fecha Cita": [
                "15/08/2026" if i % 2 == 0 else "MARZO" for i in range(1, FILAS_PASAPORTES + 1)
            ],
        }
    )

    canada = pd.DataFrame(
        {
            "NOMBRE": [f"Persona Sintetica {i:03d}" for i in range(1, FILAS_CANADA + 1)],
            "Cuenta IRCC": [f"IRCC-{i:05d}" for i in range(1, FILAS_CANADA + 1)],
            "Telefono": [f"44{i:08d}" for i in range(1, FILAS_CANADA + 1)],
            "N°Pasaporte ": [f"G{i:06d}" for i in range(1, FILAS_CANADA + 1)],
            "Cuenta Cita": [f"ca-{i:03d}" for i in range(1, FILAS_CANADA + 1)],
        }
    )

    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        # startrow=4 reproduces the four title rows that precede the real
        # header on the main sheet.
        master.to_excel(escritor, sheet_name="Master Tramex", index=False, startrow=4)
        global_entry.to_excel(escritor, sheet_name="Global entry", index=False)
        pasaportes.to_excel(escritor, sheet_name="Pasaportes", index=False)
        canada.to_excel(escritor, sheet_name="Canada", index=False)


def ejecutar_etl(archivo: Path, *extra: str) -> str:
    """Runs the pipeline and returns its output, aborting on failure."""
    resultado = subprocess.run(
        [sys.executable, "-m", "etl.etl_tramex", str(archivo), *extra],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(RAIZ)},
    )
    print(resultado.stdout)
    print(resultado.stderr, file=sys.stderr)
    if resultado.returncode != 0:
        sys.exit(f"The ETL exited with code {resultado.returncode}")
    return resultado.stdout


def contar(motor, tabla: str) -> int:
    with motor.connect() as conexion:
        return conexion.execute(text(f"SELECT count(*) FROM {tabla}")).scalar_one()


def afirmar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        sys.exit(f"::error::{mensaje}")
    print(f"  OK  {mensaje}")


def main() -> int:
    import os

    url = os.environ["DATABASE_URL"]
    motor = create_engine(url)

    with tempfile.TemporaryDirectory() as temporal:
        archivo = Path(temporal) / "TRAMEX_sintetico.xlsx"
        construir_excel(archivo)

        print("\n=== Dry run: should write nothing ===")
        ejecutar_etl(archivo, "--simulacion")
        afirmar(contar(motor, "master_tramex") == 0, "the dry run wrote no rows")

        print("\n=== First load ===")
        ejecutar_etl(archivo)
        conteos = {
            tabla: contar(motor, tabla)
            for tabla in ("clientes", "master_tramex", "global_entry", "pasaportes", "canada")
        }
        print(f"  counts: {conteos}")

        afirmar(
            conteos["master_tramex"] == FILAS_MASTER,
            f"{FILAS_MASTER} rows were loaded, and the filler and duplicate rows were discarded",
        )
        afirmar(
            conteos["clientes"] == CLIENTES_ESPERADOS,
            f"the four sheets resolved into {CLIENTES_ESPERADOS} distinct people",
        )

        print("\n=== Second load of the same file ===")
        salida = ejecutar_etl(archivo)
        conteos_finales = {tabla: contar(motor, tabla) for tabla in conteos}
        print(f"  counts: {conteos_finales}")

        afirmar(
            conteos_finales == conteos,
            "reprocessing the same file did not change any count (idempotency)",
        )
        afirmar(
            "Sin novedades" in salida,
            "the pipeline reported that the file was already reconciled",
        )

        print("\n=== Referential integrity ===")
        with motor.connect() as conexion:
            huerfanos = conexion.execute(
                text(
                    "SELECT count(*) FROM master_tramex t "
                    "LEFT JOIN clientes c ON c.id = t.cliente_id WHERE c.id IS NULL"
                )
            ).scalar_one()
            sin_cifrar = conexion.execute(
                text("SELECT count(*) FROM master_tramex WHERE contrasena_cifrada LIKE 'clave-%'")
            ).scalar_one()
            texto_libre = conexion.execute(
                text("SELECT count(*) FROM pasaportes WHERE fecha_cita_original = 'MARZO'")
            ).scalar_one()

        afirmar(huerfanos == 0, "no tramite was left without a client")
        afirmar(sin_cifrar == 0, "no credential was left in plain text")
        afirmar(texto_libre > 0, "free-text dates were preserved instead of being discarded")

    print("\nPipeline verification complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
