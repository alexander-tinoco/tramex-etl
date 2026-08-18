"""
Autenticacion, autorizacion y hashing de credenciales.

Sustituye al esquema anterior, en el que un unico administrador se autenticaba
comparando en texto plano contra dos variables de entorno. Aquel diseno tenia
tres problemas: no permitia saber *quien* hizo cada cosa (todos compartian la
misma cuenta), guardaba la contrasena en claro en el entorno y comparaba con
`!=`, que devuelve en tiempo variable y filtra informacion por temporizacion.

Ahora hay una tabla de usuarios con hash bcrypt, dos roles y sesiones JWT que
viajan por omision en una cookie `httpOnly`.
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

#: Nombre de la cookie de sesion.
COOKIE_SESION = "tramex_sesion"

# `auto_error=False` porque la sesion tambien puede venir en cookie: si el
# esquema Bearer fallara por su cuenta, nunca se llegaria a mirar la cookie.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Hashing de contrasenas
# ---------------------------------------------------------------------------


def _preparar(contrasena: str) -> bytes:
    """
    Normaliza la contrasena antes de pasarla a bcrypt.

    bcrypt trunca silenciosamente en 72 bytes, de modo que dos contrasenas
    largas que compartan prefijo serian equivalentes. Aplicar SHA-256 primero
    y codificar en base64 produce una entrada de longitud fija que evita el
    truncamiento sin perder entropia.
    """
    return base64.b64encode(hashlib.sha256(contrasena.encode("utf-8")).digest())


def hashear_contrasena(contrasena: str) -> str:
    """Devuelve el hash bcrypt de una contrasena en claro."""
    return bcrypt.hashpw(
        _preparar(contrasena), bcrypt.gensalt(rounds=settings.bcrypt_rondas)
    ).decode()


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    """
    Comprueba una contrasena contra su hash en tiempo constante.

    `bcrypt.checkpw` ya compara en tiempo constante; el `try` cubre hashes
    corruptos o con formato ajeno, que deben tratarse como fallo de
    autenticacion y no como error del servidor.
    """
    try:
        return bcrypt.checkpw(_preparar(contrasena), hash_almacenado.encode())
    except (ValueError, TypeError):
        logger.warning("Hash de contrasena con formato invalido en la base de datos")
        return False


#: Hash de descarte con el que se compara cuando el correo no existe. Sirve
#: para que un login con usuario inexistente tarde lo mismo que uno con usuario
#: real y contrasena incorrecta, y no se pueda enumerar usuarios por tiempo.
_HASH_SENUELO = hashear_contrasena(secrets.token_urlsafe(32))


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def crear_token_de_acceso(usuario: Usuario) -> str:
    """Emite un JWT de sesion con el identificador, el correo y el rol."""
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
    """Verifica firma y expiracion, devolviendo la carga util."""
    return jwt.decode(token, settings.api_secret_key, algorithms=[ALGORITMO])


# ---------------------------------------------------------------------------
# Dependencias de FastAPI
# ---------------------------------------------------------------------------

_CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesion invalida o expirada.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token_cabecera: Annotated[str | None, Depends(oauth2_scheme)] = None,
    token_cookie: Annotated[str | None, Cookie(alias=COOKIE_SESION)] = None,
) -> Usuario:
    """
    Resuelve el usuario autenticado a partir de la cookie o de la cabecera.

    Se aceptan las dos vias porque atienden a consumidores distintos: el
    dashboard usa la cookie `httpOnly` (inaccesible desde JavaScript, lo que
    reduce el impacto de un XSS), mientras que Swagger, los scripts y las
    integraciones usan `Authorization: Bearer`.

    Se comprueba tambien que el usuario siga existiendo y activo: un token
    sigue siendo criptograficamente valido despues de dar de baja a alguien, y
    sin esta verificacion esa persona conservaria acceso hasta que expirara.
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
    Construye una dependencia que exige uno de los roles indicados.

    Se devuelve una dependencia en lugar de comprobar el rol dentro de cada
    endpoint para que el requisito quede declarado en la firma de la ruta y
    aparezca en la documentacion generada.
    """

    def verificador(usuario: UsuarioActual) -> Usuario:
        if usuario.rol not in roles:
            logger.warning(
                "Acceso denegado por rol",
                extra={"usuario": usuario.correo_electronico, "rol": usuario.rol.value},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no tiene permiso para esta operacion.",
            )
        return usuario

    return verificador


RequiereAdmin = Annotated[Usuario, Depends(requiere_rol(Rol.ADMIN))]


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------


def autenticar(db: Session, correo: str, contrasena: str) -> Usuario | None:
    """
    Valida unas credenciales y devuelve el usuario, o `None` si no cuadran.

    Cuando el correo no existe se verifica igualmente contra un hash senuelo:
    asi el tiempo de respuesta no revela si la cuenta existe, que es la via
    habitual para enumerar usuarios validos antes de atacarlos.
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
    Determina la IP de origen respetando el proxy inverso.

    El dashboard se sirve detras de Nginx, asi que `request.client.host` seria
    siempre la IP del contenedor. Se toma el primer salto de
    `X-Forwarded-For`, que es el cliente real.
    """
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"
