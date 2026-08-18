"""
Router de autenticacion.

El login es el unico endpoint publico de la API y, por lo tanto, el mas
expuesto. Concentra tres controles: verificacion en tiempo constante, bloqueo
por intentos fallidos y registro en la bitacora de auditoria.
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
from app.services import auditoria, limitador
from app.services.auditoria import Accion

logger = logging.getLogger("tramex_api.auth")
router = APIRouter()


def _fijar_cookie(respuesta: Response, token: str) -> None:
    """
    Deja la sesion en una cookie `httpOnly`.

    Antes el token vivia en `localStorage`, accesible desde cualquier script de
    la pagina: un XSS bastaba para robar la sesion. Una cookie `httpOnly` no es
    legible desde JavaScript, y `SameSite` limita su envio desde otros sitios.
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
    summary="Iniciar sesion",
    description=(
        "Publico. Devuelve el token en una cookie `httpOnly` y tambien en el cuerpo, "
        "para consumidores que no usan cookies. Tras varios intentos fallidos la "
        "cuenta queda bloqueada temporalmente."
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

    # 1. Limite por origen: frena el barrido de muchas cuentas desde una IP.
    if not limitador.estado_de_ip(ip).permitido:
        auditoria.registrar(
            db,
            accion=Accion.LOGIN_BLOQUEADO,
            usuario_correo=correo,
            nivel=NivelAuditoria.ALERTA,
            request=request,
            detalle={"motivo": "limite_por_ip"},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde este origen. Intenta mas tarde.",
        )

    # 2. Bloqueo de la cuenta: protege aunque el atacante rote de IP.
    estado = limitador.estado_de_cuenta(correo)
    if not estado.permitido:
        auditoria.registrar(
            db,
            accion=Accion.LOGIN_BLOQUEADO,
            usuario_correo=correo,
            nivel=NivelAuditoria.ALERTA,
            request=request,
            detalle={"motivo": "cuenta_bloqueada", "intentos": estado.intentos},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Cuenta bloqueada temporalmente por intentos fallidos. "
                f"Vuelve a intentar en {max(1, estado.segundos_restantes // 60)} minuto(s)."
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
            detalle={"intentos_en_ventana": veredicto.intentos},
        )
        # El mensaje no distingue "no existe" de "contrasena incorrecta": decirlo
        # permitiria enumerar que cuentas son validas.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesion")
def logout(
    request: Request,
    respuesta: Response,
    db: Annotated[Session, Depends(get_db)],
    usuario: UsuarioActual,
):
    """Borra la cookie de sesion y deja constancia del cierre."""
    auditoria.registrar(db, accion=Accion.LOGOUT, usuario=usuario, request=request)
    respuesta.delete_cookie(COOKIE_SESION, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UsuarioResponse, summary="Usuario de la sesion actual")
def yo(usuario: UsuarioActual):
    """Permite al dashboard saber quien esta autenticado y con que rol."""
    return usuario


@router.post(
    "/cambiar-contrasena",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambiar la propia contrasena",
)
def cambiar_contrasena(
    request: Request,
    datos: CambioContrasena,
    db: Annotated[Session, Depends(get_db)],
    usuario: UsuarioActual,
):
    """Exige la contrasena vigente para que una sesion robada no pueda secuestrar la cuenta."""
    if not verificar_contrasena(datos.contrasena_actual, usuario.contrasena_hash):
        auditoria.registrar(
            db,
            accion=Accion.ACCESO_DENEGADO,
            usuario=usuario,
            nivel=NivelAuditoria.ADVERTENCIA,
            request=request,
            detalle={"operacion": "cambio_de_contrasena"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="La contrasena actual no coincide."
        )

    if datos.contrasena_nueva == datos.contrasena_actual:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La contrasena nueva debe ser distinta de la actual.",
        )

    crud_usuario.cambiar_contrasena(db, usuario=usuario, nueva=datos.contrasena_nueva)
    auditoria.registrar(db, accion=Accion.CONTRASENA_CAMBIADA, usuario=usuario, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
