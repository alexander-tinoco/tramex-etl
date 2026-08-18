"""
Siembra del primer administrador.

Un sistema con autenticacion real tiene un problema de arranque: nadie puede
crear el primer usuario porque crear usuarios ya exige estar autenticado. Este
script resuelve ese caso y solo ese caso.

Es idempotente: si el administrador ya existe, informa y no cambia nada. El
contenedor lo invoca al arrancar, de modo que un despliegue nuevo queda
utilizable sin pasos manuales.

Uso:
    export ADMIN_INICIAL_CORREO="admin@tuagencia.com"
    export ADMIN_INICIAL_CONTRASENA="..."     # o se genera una al vuelo
    python -m scripts.sembrar_admin
"""

from __future__ import annotations

import logging
import secrets
import sys

from app.config import settings
from app.crud import crud_usuario
from app.database import SessionLocal
from app.logging_config import setup_logging
from app.schemas import UsuarioCreate

logger = logging.getLogger("tramex_api.siembra")


def sembrar() -> int:
    """Crea el administrador inicial si aun no existe. Devuelve el codigo de salida."""
    setup_logging()
    correo = settings.admin_inicial_correo.strip().lower()

    with SessionLocal() as db:
        if crud_usuario.get_por_correo(db, correo):
            logger.info(
                "El administrador inicial ya existe; no se hace nada", extra={"correo": correo}
            )
            return 0

        contrasena = settings.admin_inicial_contrasena
        generada = contrasena is None

        if generada:
            if settings.entorno == "production":
                # En produccion, una contrasena impresa en los logs del
                # contenedor es una contrasena comprometida.
                logger.error(
                    "Define ADMIN_INICIAL_CONTRASENA. En produccion no se generan "
                    "credenciales automaticas porque acabarian en los logs."
                )
                return 1
            contrasena = secrets.token_urlsafe(18)

        crud_usuario.create(
            db,
            datos=UsuarioCreate(
                correo_electronico=correo,
                nombre="Administrador",
                contrasena=contrasena,
                rol="admin",
            ),
        )

    logger.info("Administrador inicial creado", extra={"correo": correo})
    if generada:
        # Se imprime por stdout, no por el logger estructurado, para que sea
        # facil de ver una sola vez y no quede mezclado con el resto.
        print("\n" + "=" * 60)
        print(" ADMINISTRADOR INICIAL CREADO (solo entorno de desarrollo)")
        print("=" * 60)
        print(f" Correo:     {correo}")
        print(f" Contrasena: {contrasena}")
        print(" Cambiala en el primer acceso: POST /api/v1/auth/cambiar-contrasena")
        print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(sembrar())
