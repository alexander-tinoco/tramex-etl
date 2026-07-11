"""
ETL de TRAMEX.xlsx -> base de datos operativa
==============================================

Procesa únicamente las hojas: Master Tramex, Global entry, Pasaportes, Canada.
Solo se extraen los campos definidos para cada hoja. Todo lo demás
(números de cuenta que no son contraseña, códigos de respaldo, hojas
de vacaciones, etc.) se ignora deliberadamente.

Las contraseñas (CONTRASEÑA en Master Tramex, "Número de la cuenta" en
Global entry, "Cuenta Cita" en Canada) se cifran con Fernet (AES) antes
de guardarse. Nunca se guardan ni se imprimen en texto plano.

Uso:
    export DATABASE_URL="postgresql+psycopg2://usuario:pass@host:5432/tramex"
    export TRAMEX_FERNET_KEY="<< generada con generate_key.py >>"
    python etl_tramex.py TRAMEX.xlsx

Sin DATABASE_URL, escribe a un archivo SQLite local (tramex.db) — útil
para probar antes de conectar la base real.
"""

import os
import re
import sys
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine
from cryptography.fernet import Fernet, InvalidToken

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("etl_tramex")


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Intentar cargar .env si existe en el directorio de ejecución o del script
for env_path in (".env", "etl/.env", os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")
        break

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tramex.db")
FERNET_KEY = os.environ.get("TRAMEX_FERNET_KEY")

if not FERNET_KEY:
    raise RuntimeError(
        "Falta TRAMEX_FERNET_KEY. Genera una con generate_key.py o búscala "
        "en el archivo .env e inicialízala antes de correr el ETL."
    )

fernet = Fernet(FERNET_KEY.encode())


# ---------------------------------------------------------------------------
# Utilidades de limpieza (compartidas entre hojas)
# ---------------------------------------------------------------------------

def clean_text(value):
    """Recorta espacios y convierte vacíos/NaN a None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def clean_phone(value):
    """Deja solo dígitos. No asume longitud fija por los distintos formatos vistos."""
    if pd.isna(value):
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if digits else None


def clean_email(value):
    """Normaliza a minúsculas y descarta lo que no tiene forma de correo."""
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if "@" not in text or " " in text:
        logger.warning("Correo con formato inválido descartado: %r", text)
        return None
    return text


def encrypt_value(value):
    """Cifra un valor sensible (contraseña). Nunca regresa el texto plano."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return fernet.encrypt(text.encode()).decode()


def parse_date_or_keep_raw(value):
    """
    Algunas celdas de fecha traen texto libre (ej. 'MARZO') en vez de una
    fecha real. Regresa (fecha_parseada_o_None, texto_original_o_None).
    """
    if pd.isna(value):
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    text = str(value).strip()
    if not text:
        return None, None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date(), None
        except ValueError:
            continue
    logger.warning("Fecha no reconocida, se conserva como texto: %r", text)
    return None, text


# ---------------------------------------------------------------------------
# Extract + Transform por hoja
# ---------------------------------------------------------------------------

def etl_master_tramex(xls_path):
    # El encabezado real vive en la fila 5 de la hoja (header=4, 0-indexado)
    df = pd.read_excel(xls_path, sheet_name="Master Tramex", header=4)
    df = df.rename(columns={
        "NOMBRE": "nombre",
        "ID ": "id_solicitud",
        "Telefono": "telefono",
        "N°Pasaporte ": "numero_pasaporte",
        "TRAMITE": "tramite",
        "CITA ": "cita",
        "Correo electrónico": "correo_electronico",
        "CONTRASEÑA": "contrasena",
    })

    columnas = ["nombre", "id_solicitud", "telefono", "numero_pasaporte",
                "tramite", "cita", "correo_electronico", "contrasena"]
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise ValueError(f"Master Tramex: no encontré estas columnas: {faltantes}")

    df = df[columnas].copy()
    df = df[df["nombre"].notna()]  # descarta filas vacías / de relleno

    df["nombre"] = df["nombre"].map(clean_text)
    df["id_solicitud"] = df["id_solicitud"].map(clean_text)
    df["telefono"] = df["telefono"].map(clean_phone)
    df["numero_pasaporte"] = df["numero_pasaporte"].map(clean_text)
    df["tramite"] = df["tramite"].map(clean_text)
    df["cita"] = df["cita"].map(clean_text)
    df["correo_electronico"] = df["correo_electronico"].map(clean_email)
    df["contrasena_cifrada"] = df["contrasena"].map(encrypt_value)
    df = df.drop(columns=["contrasena"])

    df = df.dropna(subset=["nombre"]).drop_duplicates()
    logger.info("Master Tramex: %d filas listas", len(df))
    return df


def etl_global_entry(xls_path):
    df = pd.read_excel(xls_path, sheet_name="Global entry", header=0)
    df = df.rename(columns={
        "Nombre": "nombre",
        "Apellido ": "apellido",
        "Correo electrónico": "correo_electronico",
        "Número de pasaporte": "numero_pasaporte",
        "Número de la cuenta": "contrasena",  # en la práctica se usa como contraseña
    })

    columnas = ["nombre", "apellido", "correo_electronico", "numero_pasaporte", "contrasena"]
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise ValueError(f"Global entry: no encontré estas columnas: {faltantes}")

    df = df[columnas].copy()
    df = df[df["nombre"].notna()]

    df["nombre"] = df["nombre"].map(clean_text)
    df["apellido"] = df["apellido"].map(clean_text)
    df["correo_electronico"] = df["correo_electronico"].map(clean_email)
    df["numero_pasaporte"] = df["numero_pasaporte"].map(clean_text)
    df["contrasena_cifrada"] = df["contrasena"].map(encrypt_value)
    df = df.drop(columns=["contrasena"])

    df = df.dropna(subset=["nombre"]).drop_duplicates()
    logger.info("Global entry: %d filas listas", len(df))
    return df


def etl_pasaportes(xls_path):
    df = pd.read_excel(xls_path, sheet_name="Pasaportes", header=0)
    df = df.rename(columns={
        "Nombre": "nombre",
        "Apellido ": "apellido",
        "Teléfono": "telefono",
        "Lugar de la cita": "lugar_cita",
        "Fecha Cita": "fecha_cita_raw",
    })
    # "No. cita" se excluye a propósito, no se incluye en columnas

    columnas = ["nombre", "apellido", "telefono", "lugar_cita", "fecha_cita_raw"]
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise ValueError(f"Pasaportes: no encontré estas columnas: {faltantes}")

    df = df[columnas].copy()
    df = df[df["nombre"].notna()]

    df["nombre"] = df["nombre"].map(clean_text)
    df["apellido"] = df["apellido"].map(clean_text)
    df["telefono"] = df["telefono"].map(clean_phone)
    df["lugar_cita"] = df["lugar_cita"].map(clean_text)

    fechas = df["fecha_cita_raw"].map(parse_date_or_keep_raw)
    df["fecha_cita"] = fechas.map(lambda t: t[0])
    df["fecha_cita_original"] = fechas.map(lambda t: t[1])
    df = df.drop(columns=["fecha_cita_raw"])

    df = df.dropna(subset=["nombre"]).drop_duplicates()
    logger.info("Pasaportes: %d filas listas", len(df))
    return df


def etl_canada(xls_path):
    df = pd.read_excel(xls_path, sheet_name="Canada", header=0)
    df = df.rename(columns={
        "NOMBRE": "nombre",
        "Cuenta IRCC": "cuenta_ircc",
        "Telefono": "telefono",
        "N°Pasaporte ": "numero_pasaporte",
        "Cuenta Cita": "contrasena",  # en la práctica se usa como contraseña
    })

    columnas = ["nombre", "cuenta_ircc", "telefono", "numero_pasaporte", "contrasena"]
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise ValueError(f"Canada: no encontré estas columnas: {faltantes}")

    df = df[columnas].copy()
    df = df[df["nombre"].notna()]

    df["nombre"] = df["nombre"].map(clean_text)
    df["cuenta_ircc"] = df["cuenta_ircc"].map(clean_text)
    df["telefono"] = df["telefono"].map(clean_phone)
    df["numero_pasaporte"] = df["numero_pasaporte"].map(clean_text)
    df["contrasena_cifrada"] = df["contrasena"].map(encrypt_value)
    df = df.drop(columns=["contrasena"])

    df = df.dropna(subset=["nombre"]).drop_duplicates()
    logger.info("Canada: %d filas listas", len(df))
    return df


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load(engine, table_name, df):
    df.to_sql(table_name, engine, if_exists="append", index=False)
    logger.info("Cargadas %d filas en '%s'", len(df), table_name)


def main():
    if len(sys.argv) != 2:
        print("Uso: python etl_tramex.py <ruta al TRAMEX.xlsx>")
        sys.exit(1)

    xls_path = sys.argv[1]
    engine = create_engine(DATABASE_URL)

    tablas = {
        "master_tramex": etl_master_tramex(xls_path),
        "global_entry": etl_global_entry(xls_path),
        "pasaportes": etl_pasaportes(xls_path),
        "canada": etl_canada(xls_path),
    }

    for nombre_tabla, df in tablas.items():
        load(engine, nombre_tabla, df)

    logger.info("ETL completado contra %s", DATABASE_URL)


if __name__ == "__main__":
    main()
