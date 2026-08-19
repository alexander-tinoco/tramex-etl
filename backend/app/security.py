"""
Authentication, authorization, and credential hashing.

Replaces the previous scheme, in which a single administrator authenticated
by comparing plain text against two environment variables. That design had
three problems: it gave no way to know *who* did each thing (everyone shared
the same account), it kept the password in plain text in the environment, and
it compared with `!=`, which returns in variable time and leaks information
through timing.

Now there's a users table with bcrypt hashes, two roles, and JWT sessions
that travel by default in an `httpOnly` cookie.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Rol, Usuario

logger = logging.getLogger("tramex_api.security")

ALGORITMO = "HS256"

#: Session cookie name.
COOKIE_SESION = "tramex_sesion"

# `auto_error=False` because the session can also arrive in a cookie: if the
# Bearer scheme failed on its own, the cookie would never get checked.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def _preparar(contrasena: str) -> bytes:
    """
    Normalizes the password before handing it to bcrypt.

    bcrypt silently truncates at 72 bytes, so two long passwords sharing a
    prefix would be treated as equivalent. Applying SHA-256 first and
    base64-encoding it produces a fixed-length input that avoids the
    truncation without losing entropy.
    """
    return base64.b64encode(hashlib.sha256(contrasena.encode("utf-8")).digest())


def hashear_contrasena(contrasena: str) -> str:
    """Returns the bcrypt hash of a plain-text password."""
    return bcrypt.hashpw(
        _preparar(contrasena), bcrypt.gensalt(rounds=settings.bcrypt_rondas)
    ).decode()


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    """
    Checks a password against its hash in constant time.

    `bcrypt.checkpw` already compares in constant time; the `try` covers
    corrupted hashes or ones with an unexpected format, which must be
    treated as an authentication failure, not a server error.
    """
    try:
        return bcrypt.checkpw(_preparar(contrasena), hash_almacenado.encode())
    except (ValueError, TypeError):
        logger.warning("Password hash with invalid format in the database")
        return False


#: Decoy hash to compare against when the email doesn't exist. Makes a login
#: with a nonexistent user take as long as one with a real user and a wrong
#: password, so users can't be enumerated by timing.
_HASH_SENUELO = hashear_contrasena(secrets.token_urlsafe(32))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def crear_token_de_acceso(usuario: Usuario) -> str:
    """Issues a session JWT with the id, email, and role."""
    expira = datetime.now(UTC) + timedelta(minutes=settings.token_expira_minutos)
    carga = {
        "sub": str(usuario.id),
        "correo": usuario.correo_electronico,
        "rol": usuario.rol.value,
        "exp": expira,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(carga, settings.api_secret_key, algorithm=ALGORITMO)


def decodificar_token(token: str) -> dict:
    """Verifies the signature and expiration, and returns the payload."""
    return jwt.decode(token, settings.api_secret_key, algorithms=[ALGORITMO])


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired session.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token_cabecera: Annotated[str | None, Depends(oauth2_scheme)] = None,
    token_cookie: Annotated[str | None, Cookie(alias=COOKIE_SESION)] = None,
) -> Usuario:
    """
    Resolves the authenticated user from the cookie or the header.

    Both routes are accepted because they serve different consumers: the
    dashboard uses the `httpOnly` cookie (inaccessible from JavaScript, which
    reduces the impact of an XSS), while Swagger, scripts, and integrations
    use `Authorization: Bearer`.

    It also checks that the user still exists and is active: a token remains
    cryptographically valid after someone is deactivated, and without this
    check that person would keep access until it expired.
    """
    token = token_cookie or token_cabecera
    if not token:
        raise _CREDENCIALES_INVALIDAS

    try:
        carga = decodificar_token(token)
        usuario_id = int(carga["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise _CREDENCIALES_INVALIDAS from exc

    usuario = db.scalar(select(Usuario).where(Usuario.id == usuario_id))
    if usuario is None or not usuario.activo or usuario.eliminado_en is not None:
        raise _CREDENCIALES_INVALIDAS
    return usuario


UsuarioActual = Annotated[Usuario, Depends(get_current_user)]


def requiere_rol(*roles: Rol):
    """
    Builds a dependency that requires one of the given roles.

    A dependency is returned instead of checking the role inside each
    endpoint so the requirement is declared in the route's signature and
    shows up in the generated documentation.
    """

    def verificador(usuario: UsuarioActual) -> Usuario:
        if usuario.rol not in roles:
            logger.warning(
                "Access denied by role",
                extra={"usuario": usuario.correo_electronico, "rol": usuario.rol.value},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not have permission for this operation.",
            )
        return usuario

    return verificador


RequiereAdmin = Annotated[Usuario, Depends(requiere_rol(Rol.ADMIN))]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def autenticar(db: Session, correo: str, contrasena: str) -> Usuario | None:
    """
    Validates a set of credentials and returns the user, or `None` if they don't match.

    When the email doesn't exist, it's still checked against a decoy hash:
    that way the response time doesn't reveal whether the account exists,
    which is the usual way to enumerate valid users before attacking them.
    """
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.correo_electronico == correo.strip().lower(),
            Usuario.eliminado_en.is_(None),
        )
    )

    if usuario is None:
        verificar_contrasena(contrasena, _HASH_SENUELO)
        return None

    if not verificar_contrasena(contrasena, usuario.contrasena_hash):
        return None

    if not usuario.activo:
        return None

    return usuario


def obtener_ip(request: Request) -> str:
    """
    Determines the source IP, accounting for the reverse proxy.

    The dashboard is served behind Nginx, so `request.client.host` would
    always be the container's IP. The first hop of `X-Forwarded-For` is
    taken instead, which is the real client.
    """
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
