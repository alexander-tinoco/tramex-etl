"""
ETL pipeline configuration.

The ETL runs as a standalone process (an operator launches it from their
machine, or a scheduled job runs it), so it doesn't share the API's
configuration object. What it does share is the contract: the same variable
names and the same Fernet key, because it writes to the same tables.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger("etl.config")

#: Paths where a .env file is looked for, in priority order.
RUTAS_ENV = (
    Path(".env"),
    Path("etl/.env"),
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
)


class ErrorDeConfiguracion(Exception):
    """Required configuration to run the pipeline is missing."""


def cargar_dotenv() -> None:
    """
    Loads the first `.env` that exists, without overwriting what's already
    in the environment.

    Real environment variables take priority over the file: that's what lets
    the same command work locally (reading `.env`) and in a container
    (receiving injected secrets).
    """
    for ruta in RUTAS_ENV:
        if not ruta.is_file():
            continue
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            clave = clave.strip()
            if clave not in os.environ:
                os.environ[clave] = valor.strip().strip("'\"")
        logger.debug("Configuration loaded from %s", ruta)
        return


def obtener_url_base_de_datos() -> str:
    """
    Returns the connection string.

    Unlike the previous version, there is **no** silent fallback to a local
    SQLite database: writing to `tramex.db` while thinking you're writing to
    the real database is an expensive failure that's hard to notice. If the
    variable is missing, it says so.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ErrorDeConfiguracion(
            "DATABASE_URL is missing. Set the PostgreSQL connection string before "
            "loading, for example:\n"
            "  export DATABASE_URL='postgresql+psycopg2://postgres:...@localhost:5434/tramex'"
        )
    return url


def obtener_fernet() -> Fernet:
    """Builds the cipher, verifying the key is usable."""
    llave = os.environ.get("TRAMEX_FERNET_KEY")
    if not llave:
        raise ErrorDeConfiguracion(
            "TRAMEX_FERNET_KEY is missing. Generate one with `python etl/generate_key.py` "
            "and save it in the secrets manager; without it, client credentials can't "
            "be encrypted."
        )
    try:
        return Fernet(llave.encode())
    except Exception as exc:
        raise ErrorDeConfiguracion(
            "TRAMEX_FERNET_KEY is not a valid Fernet key. It must be a 32-byte key "
            "in url-safe base64, like the one generate_key.py produces."
        ) from exc


def configurar_logging(nivel: str = "INFO") -> None:
    """Sets up the pipeline's logs in a console-legible format."""
    logging.basicConfig(
        level=nivel.upper(),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
