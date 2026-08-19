"""
Seeding the first administrator.

A system with real authentication has a bootstrapping problem: nobody can
create the first user because creating users already requires being
authenticated. This script solves that one case, and only that case.

It's idempotent: if the administrator already exists, it reports that and
changes nothing. The container invokes it on startup, so a fresh deployment
ends up usable with no manual steps.

Usage:
    export ADMIN_INICIAL_CORREO="admin@youragency.com"
    export ADMIN_INICIAL_CONTRASENA="..."     # or one is generated on the fly
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
    """Creates the initial administrator if it doesn't exist yet. Returns the exit code."""
    setup_logging()
    correo = settings.admin_inicial_correo.strip().lower()

    with SessionLocal() as db:
        if crud_usuario.get_por_correo(db, correo):
            logger.info(
                "The initial administrator already exists; nothing to do", extra={"correo": correo}
            )
            return 0

        contrasena = settings.admin_inicial_contrasena
        generada = contrasena is None

        if generada:
            if settings.entorno == "production":
                # In production, a password printed to the container logs
                # is a compromised password.
                logger.error(
                    "Set ADMIN_INICIAL_CONTRASENA. In production, credentials are not "
                    "generated automatically because they'd end up in the logs."
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

    logger.info("Initial administrator created", extra={"correo": correo})
    if generada:
        # Printed to stdout, not through the structured logger, so it's
        # easy to see once and doesn't get mixed in with the rest.
        print("\n" + "=" * 60)
        print(" INITIAL ADMINISTRATOR CREATED (development environment only)")
        print("=" * 60)
        print(f" Email:    {correo}")
        print(f" Password: {contrasena}")
        print(" Change it on first sign-in: POST /api/v1/auth/cambiar-contrasena")
        print("=" * 60 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(sembrar())
