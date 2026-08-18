"""
Configuracion del pipeline ETL.

El ETL corre como proceso suelto (una operadora lo lanza desde su maquina o un
job programado lo ejecuta), asi que no comparte el objeto de configuracion de
la API. Lo que si comparte es el contrato: los mismos nombres de variables y la
misma llave Fernet, porque escribe en las mismas tablas.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger("etl.config")

#: Rutas donde se busca un archivo .env, en orden de prioridad.
RUTAS_ENV = (
    Path(".env"),
    Path("etl/.env"),
    Path(__file__).resolve().parent.parent / ".env",
    Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
)


class ErrorDeConfiguracion(Exception):
    """Falta configuracion obligatoria para ejecutar el pipeline."""


def cargar_dotenv() -> None:
    """
    Carga el primer `.env` que exista, sin pisar lo que ya venga del entorno.

    Las variables reales del entorno tienen prioridad sobre el archivo: es lo
    que permite que el mismo comando funcione en local (leyendo `.env`) y en un
    contenedor (recibiendo secretos inyectados).
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
        logger.debug("Configuracion cargada desde %s", ruta)
        return


def obtener_url_base_de_datos() -> str:
    """
    Devuelve la cadena de conexion.

    A diferencia de la version anterior, **no** hay respaldo silencioso a un
    SQLite local: escribir en `tramex.db` creyendo que se escribia en la base
    real es un fallo caro y dificil de notar. Si falta la variable, se dice.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ErrorDeConfiguracion(
            "Falta DATABASE_URL. Define la conexion a PostgreSQL antes de cargar, "
            "por ejemplo:\n"
            "  export DATABASE_URL='postgresql+psycopg2://postgres:...@localhost:5434/tramex'"
        )
    return url


def obtener_fernet() -> Fernet:
    """Construye el cifrador, verificando que la llave sea utilizable."""
    llave = os.environ.get("TRAMEX_FERNET_KEY")
    if not llave:
        raise ErrorDeConfiguracion(
            "Falta TRAMEX_FERNET_KEY. Genera una con `python etl/generate_key.py` y "
            "guardala en el gestor de secretos; sin ella las credenciales de los "
            "clientes no pueden cifrarse."
        )
    try:
        return Fernet(llave.encode())
    except Exception as exc:
        raise ErrorDeConfiguracion(
            "TRAMEX_FERNET_KEY no es una llave Fernet valida. Debe ser una llave "
            "de 32 bytes en base64 url-safe, como la que genera generate_key.py."
        ) from exc


def configurar_logging(nivel: str = "INFO") -> None:
    """Deja los logs del pipeline en un formato legible en consola."""
    logging.basicConfig(
        level=nivel.upper(),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
