"""
Authentication router.

Login is the API's only public endpoint and, therefore, the most exposed. It
concentrates three controls: constant-time verification, lockout after
failed attempts, and audit logging.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.crud import crud_usuario
from app.database import get_db
from app.models import NivelAuditoria
from app.schemas import CambioContrasena, TokenResponse, UsuarioResponse
from app.security import (
    COOKIE_SESION,
    UsuarioActual,
    autenticar,
    crear_token_de_acceso,
    obtener_ip,
    verificar_contrasena,
)
from app.services import auditoria, limitador, metricas
from app.services.auditoria import Accion

logger = logging.getLogger("tramex_api.auth")
router = APIRouter()


def _fijar_cookie(respuesta: Response, token: str) -> None:
    """
    Leaves the session in an `httpOnly` cookie.

    The token used to live in `localStorage`, reachable from any script on
    the page: an XSS was enough to steal the session. An `httpOnly` cookie
    can't be read from JavaScript, and `SameSite` limits it being sent from
    other sites.
    """
    respuesta.set_cookie(
        key=COOKIE_SESION,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.token_expira_minutos * 60,
        path="/",
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Sign in",
    description=(
        "Public. Returns the token in an `httpOnly` cookie and also in the "
        "body, for consumers that don't use cookies. After several failed "
        "attempts the account is temporarily locked."
    ),
)
def login(
    request: Request,
    respuesta: Response,
    db: Annotated[Session, Depends(get_db)],
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    correo = formulario.username
    ip = obtener_ip(request)

    # 1. Origin limit: slows down sweeping many accounts from one IP.
    if not limitador.estado_de_ip(ip).permitido:
        auditoria.registrar(
            db,
            accion=Accion.LOGIN_BLOQUEADO,
            usuario_correo=correo,
            nivel=NivelAuditoria.ALERTA,
            request=request,
            detalle={"reason": "rate_limited_by_ip"},
        )
        metricas.intentos_de_login.labels(resultado="blocked_by_ip").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts from this origin. Try again later.",
        )

    # 2. Account lockout: protects even if the attacker rotates IPs.
    estado = limitador.estado_de_cuenta(correo)
    if not estado.permitido:
        auditoria.registrar(
            db,
            accion=Accion.LOGIN_BLOQUEADO,
            usuario_correo=correo,
            nivel=NivelAuditoria.ALERTA,
            request=request,
            detalle={"reason": "account_locked", "attempts": estado.intentos},
        )
        metricas.intentos_de_login.labels(resultado="account_locked").inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Account temporarily locked due to failed attempts. "
                f"Try again in {max(1, estado.segundos_restantes // 60)} minute(s)."
            ),
        )

    usuario = autenticar(db, correo, formulario.password)

    if usuario is None:
        veredicto = limitador.registrar_fallo(correo, ip)
        auditoria.registrar(
            db,
            accion=Accion.LOGIN_FALLIDO,
            usuario_correo=correo,
            nivel=NivelAuditoria.ADVERTENCIA,
            request=request,
            detalle={"attempts_in_window": veredicto.intentos},
        )
        metricas.intentos_de_login.labels(resultado="failed").inc()
        # The message doesn't distinguish "doesn't exist" from "wrong
        # password": saying so would let someone enumerate which accounts
        # are valid.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    metricas.intentos_de_login.labels(resultado="successful").inc()
    limitador.registrar_exito(correo)
    crud_usuario.registrar_acceso(db, usuario=usuario)
    auditoria.registrar(db, accion=Accion.LOGIN_EXITOSO, usuario=usuario, request=request)

    token = crear_token_de_acceso(usuario)
    _fijar_cookie(respuesta, token)

    return TokenResponse(
        access_token=token,
        expira_en_minutos=settings.token_expira_minutos,
        usuario=UsuarioResponse.model_validate(usuario),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
def logout(
    request: Request,
    respuesta: Response,
    db: Annotated[Session, Depends(get_db)],
    usuario: UsuarioActual,
):
    """Clears the session cookie and logs the sign-out."""
    auditoria.registrar(db, accion=Accion.LOGOUT, usuario=usuario, request=request)
    respuesta.delete_cookie(COOKIE_SESION, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UsuarioResponse, summary="Current session's user")
def yo(usuario: UsuarioActual):
    """Lets the dashboard know who is authenticated and with what role."""
    return usuario


@router.post(
    "/cambiar-contrasena",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change your own password",
)
def cambiar_contrasena(
    request: Request,
    datos: CambioContrasena,
    db: Annotated[Session, Depends(get_db)],
    usuario: UsuarioActual,
):
    """Requires the current password so a stolen session can't hijack the account."""
    if not verificar_contrasena(datos.contrasena_actual, usuario.contrasena_hash):
        auditoria.registrar(
            db,
            accion=Accion.ACCESO_DENEGADO,
            usuario=usuario,
            nivel=NivelAuditoria.ADVERTENCIA,
            request=request,
            detalle={"operation": "password_change"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="The current password doesn't match."
        )

    if datos.contrasena_nueva == datos.contrasena_actual:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The new password must be different from the current one.",
        )

    crud_usuario.cambiar_contrasena(db, usuario=usuario, nueva=datos.contrasena_nueva)
    auditoria.registrar(db, accion=Accion.CONTRASENA_CAMBIADA, usuario=usuario, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
