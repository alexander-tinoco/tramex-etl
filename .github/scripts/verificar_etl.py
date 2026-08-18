#!/usr/bin/env python3
"""
Verificacion de extremo a extremo del pipeline ETL en la integracion continua.

Las pruebas unitarias del ETL corren sobre SQLite y con DataFrames construidos a
mano. Este script comprueba lo que aquellas no pueden: que el pipeline completo
funcione contra PostgreSQL real, leyendo un archivo Excel de verdad, y que
reprocesarlo **no duplique nada**, que es la propiedad que motivo su reescritura.

Los datos son sinteticos. El archivo real contiene informacion personal de
clientes y nunca debe entrar al repositorio ni a un runner.
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
#: Personas distintas esperadas: todas las hojas describen a la misma gente.
CLIENTES_ESPERADOS = FILAS_MASTER


def construir_excel(destino: Path) -> None:
    """Genera un libro con la estructura y las rarezas del archivo real."""
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
    # Rarezas reales del archivo: filas de relleno sin nombre y una captura
    # duplicada de la misma persona con distinto espaciado y capitalizacion.
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
            # Mezcla de fechas validas y texto libre, como el archivo real.
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
        # startrow=4 reproduce las cuatro filas de titulos que preceden al
        # encabezado real en la hoja principal.
        master.to_excel(escritor, sheet_name="Master Tramex", index=False, startrow=4)
        global_entry.to_excel(escritor, sheet_name="Global entry", index=False)
        pasaportes.to_excel(escritor, sheet_name="Pasaportes", index=False)
        canada.to_excel(escritor, sheet_name="Canada", index=False)


def ejecutar_etl(archivo: Path, *extra: str) -> str:
    """Corre el pipeline y devuelve su salida, abortando si falla."""
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
        sys.exit(f"El ETL termino con codigo {resultado.returncode}")
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

        print("\n=== Simulacion: no debe escribir nada ===")
        ejecutar_etl(archivo, "--simulacion")
        afirmar(contar(motor, "master_tramex") == 0, "la simulacion no escribio ninguna fila")

        print("\n=== Primera carga ===")
        ejecutar_etl(archivo)
        conteos = {
            tabla: contar(motor, tabla)
            for tabla in ("clientes", "master_tramex", "global_entry", "pasaportes", "canada")
        }
        print(f"  conteos: {conteos}")

        afirmar(
            conteos["master_tramex"] == FILAS_MASTER,
            f"se cargaron {FILAS_MASTER} filas y se descartaron las de relleno y la duplicada",
        )
        afirmar(
            conteos["clientes"] == CLIENTES_ESPERADOS,
            f"las cuatro hojas se resolvieron en {CLIENTES_ESPERADOS} personas distintas",
        )

        print("\n=== Segunda carga del mismo archivo ===")
        salida = ejecutar_etl(archivo)
        conteos_finales = {tabla: contar(motor, tabla) for tabla in conteos}
        print(f"  conteos: {conteos_finales}")

        afirmar(
            conteos_finales == conteos,
            "reprocesar el mismo archivo no cambio ningun conteo (idempotencia)",
        )
        afirmar(
            "Sin novedades" in salida,
            "el pipeline reporto que el archivo ya estaba conciliado",
        )

        print("\n=== Integridad referencial ===")
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

        afirmar(huerfanos == 0, "ningun tramite quedo sin cliente")
        afirmar(sin_cifrar == 0, "ninguna credencial quedo en texto plano")
        afirmar(texto_libre > 0, "las fechas en texto libre se preservaron en vez de descartarse")

    print("\nVerificacion del pipeline completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
