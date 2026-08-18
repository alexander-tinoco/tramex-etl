"""
Router administrativo: usuarios, bitacora de auditoria y retencion.

Todas sus rutas exigen rol `admin`. La separacion importa: una operadora
necesita consultar credenciales de clientes para hacer su trabajo, pero no debe
poder crear cuentas, leer quien consulto que ni destruir el historial.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.crud import (
    crud_canada,
    crud_cliente,
    crud_global,
    crud_master,
    crud_pasaporte,
    crud_usuario,
)
from app.database import get_db
from app.models import NivelAuditoria
from app.schemas import (
    LogAuditoriaResponse,
    PaginatedResponse,
    ResultadoRetencion,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.security import RequiereAdmin
from app.services import auditoria
from app.services.auditoria import Accion

router = APIRouter()

REPOSITORIOS = {
    "clientes": crud_cliente,
    "master_tramex": crud_master,
    "global_entry": crud_global,
    "pasaportes": crud_pasaporte,
    "canada": crud_canada,
}


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------


@router.get(
    "/usuarios", response_model=PaginatedResponse[UsuarioResponse], summary="Listar usuarios"
)
def listar_usuarios(
    db: Annotated[Session, Depends(get_db)],
    _: RequiereAdmin,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    usuarios, total = crud_usuario.get_multi(db, skip=skip, limit=limit)
    return {"total": total, "skip": skip, "limit": limit, "items": usuarios}


@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta un usuario",
)
def crear_usuario(
    request: Request,
    datos: UsuarioCreate,
    db: Annotated[Session, Depends(get_db)],
    admin: RequiereAdmin,
):
    if crud_usuario.get_por_correo(db, datos.correo_electronico):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo.",
        )

    usuario = crud_usuario.create(db, datos=datos)
    auditoria.registrar(
        db,
        accion=Accion.USUARIO_CREADO,
        usuario=admin,
        recurso="usuarios",
        registro_id=usuario.id,
        request=request,
        detalle={"correo_creado": usuario.correo_electronico, "rol": usuario.rol.value},
    )
    return usuario


@router.patch(
    "/usuarios/{usuario_id}", response_model=UsuarioResponse, summary="Actualizar un usuario"
)
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: RequiereAdmin,
):
    usuario = crud_usuario.get(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario inexistente.")

    # Degradar o desactivar al ultimo administrador dejaria el sistema sin
    # nadie capaz de administrarlo, y recuperarlo exigiria tocar la base a mano.
    quita_admin = (datos.rol is not None and datos.rol != "admin") or datos.activo is False
    if usuario.es_admin and quita_admin and crud_usuario.contar_admins_activos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes dejar el sistema sin ningun administrador activo.",
        )

    return crud_usuario.update(db, usuario=usuario, datos=datos)


@router.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dar de baja un usuario",
)
def desactivar_usuario(
    usuario_id: int, db: Annotated[Session, Depends(get_db)], admin: RequiereAdmin
):
    usuario = crud_usuario.get(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario inexistente.")
    if usuario.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No puedes darte de baja a ti mismo."
        )
    if usuario.es_admin and crud_usuario.contar_admins_activos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puedes dejar el sistema sin ningun administrador activo.",
        )

    crud_usuario.desactivar(db, usuario=usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Bitacora de auditoria
# ---------------------------------------------------------------------------


@router.get(
    "/auditoria",
    response_model=PaginatedResponse[LogAuditoriaResponse],
    summary="Consultar la bitacora de auditoria",
    description=(
        "Historial de eventos sensibles, del mas reciente al mas antiguo. "
        "Ningun asiento contiene credenciales: se registra que se consulto, "
        "nunca que se obtuvo."
    ),
)
def consultar_auditoria(
    db: Annotated[Session, Depends(get_db)],
    _: RequiereAdmin,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    accion: Annotated[str | None, Query(description="Filtra por tipo de evento.")] = None,
    usuario_id: Annotated[int | None, Query(description="Filtra por autor.")] = None,
    nivel: Annotated[NivelAuditoria | None, Query(description="Filtra por severidad.")] = None,
    ultimos_dias: Annotated[
        int | None, Query(ge=1, le=365, description="Acota a los ultimos N dias.")
    ] = None,
):
    desde = datetime.now(UTC) - timedelta(days=ultimos_dias) if ultimos_dias else None
    asientos, total = auditoria.consultar(
        db, skip=skip, limit=limit, accion=accion, usuario_id=usuario_id, nivel=nivel, desde=desde
    )
    return {"total": total, "skip": skip, "limit": limit, "items": asientos}


# ---------------------------------------------------------------------------
# Retencion
# ---------------------------------------------------------------------------


@router.post(
    "/retencion/ejecutar",
    response_model=ResultadoRetencion,
    summary="Aplicar la politica de retencion",
    description=(
        "Destruye definitivamente los registros archivados hace mas de "
        "`DIAS_RETENCION` dias, y los asientos de auditoria fuera de ese periodo. "
        "Es la unica operacion del sistema que borra datos de forma irreversible."
    ),
)
def ejecutar_retencion(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: RequiereAdmin,
    confirmar: Annotated[
        bool, Query(description="Debe ser true; evita ejecuciones accidentales.")
    ] = False,
):
    if not confirmar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "La purga es irreversible. Repite la llamada con `confirmar=true` para ejecutarla."
            ),
        )

    corte = datetime.now(UTC) - timedelta(days=settings.dias_retencion)
    purgados = {
        nombre: repositorio.purgar_vencidos(db, antes_de=corte)
        for nombre, repositorio in REPOSITORIOS.items()
    }
    asientos = auditoria.purgar_anteriores_a(db, settings.dias_retencion)
    total = sum(purgados.values())

    auditoria.registrar(
        db,
        accion=Accion.REGISTRO_PURGADO,
        usuario=admin,
        nivel=NivelAuditoria.ALERTA,
        request=request,
        detalle={
            "dias_retencion": settings.dias_retencion,
            "registros_purgados": total,
            "asientos_purgados": asientos,
        },
    )

    return ResultadoRetencion(
        dias_retencion=settings.dias_retencion,
        purgados_por_tabla=purgados,
        asientos_de_auditoria_purgados=asientos,
        total_purgado=total,
    )
