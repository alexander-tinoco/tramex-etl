"""
Administrative router: users, audit log and retention.

All its routes require the `admin` role. The separation matters: an operator
needs to look up client credentials to do their job, but must not be able to
create accounts, read who queried what, or destroy the history.
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
# Users
# ---------------------------------------------------------------------------


@router.get("/usuarios", response_model=PaginatedResponse[UsuarioResponse], summary="List users")
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
    summary="Create a user",
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
            detail="A user with that email already exists.",
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


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioResponse, summary="Update a user")
def actualizar_usuario(
    usuario_id: int,
    datos: UsuarioUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: RequiereAdmin,
):
    usuario = crud_usuario.get(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Demoting or deactivating the last administrator would leave the system
    # with no one able to administer it, and recovering from that would
    # require touching the database by hand.
    quita_admin = (datos.rol is not None and datos.rol != "admin") or datos.activo is False
    if usuario.es_admin and quita_admin and crud_usuario.contar_admins_activos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot leave the system with no active administrator.",
        )

    return crud_usuario.update(db, usuario=usuario, datos=datos)


@router.delete(
    "/usuarios/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user",
)
def desactivar_usuario(
    usuario_id: int, db: Annotated[Session, Depends(get_db)], admin: RequiereAdmin
):
    usuario = crud_usuario.get(db, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if usuario.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You cannot deactivate yourself."
        )
    if usuario.es_admin and crud_usuario.contar_admins_activos(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot leave the system with no active administrator.",
        )

    crud_usuario.desactivar(db, usuario=usuario)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@router.get(
    "/auditoria",
    response_model=PaginatedResponse[LogAuditoriaResponse],
    summary="Query the audit log",
    description=(
        "History of sensitive events, most recent first. No entry ever "
        "contains credentials: what's logged is that something was looked "
        "up, never what was obtained."
    ),
)
def consultar_auditoria(
    db: Annotated[Session, Depends(get_db)],
    _: RequiereAdmin,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    accion: Annotated[str | None, Query(description="Filters by event type.")] = None,
    usuario_id: Annotated[int | None, Query(description="Filters by author.")] = None,
    nivel: Annotated[NivelAuditoria | None, Query(description="Filters by severity.")] = None,
    ultimos_dias: Annotated[
        int | None, Query(ge=1, le=365, description="Limits to the last N days.")
    ] = None,
):
    desde = datetime.now(UTC) - timedelta(days=ultimos_dias) if ultimos_dias else None
    asientos, total = auditoria.consultar(
        db, skip=skip, limit=limit, accion=accion, usuario_id=usuario_id, nivel=nivel, desde=desde
    )
    return {"total": total, "skip": skip, "limit": limit, "items": asientos}


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


@router.post(
    "/retencion/ejecutar",
    response_model=ResultadoRetencion,
    summary="Apply the retention policy",
    description=(
        "Permanently destroys records archived more than `DIAS_RETENCION` "
        "days ago, and audit entries outside that window. This is the only "
        "operation in the system that deletes data irreversibly."
    ),
)
def ejecutar_retencion(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: RequiereAdmin,
    confirmar: Annotated[
        bool, Query(description="Must be true; prevents accidental runs.")
    ] = False,
):
    if not confirmar:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("The purge is irreversible. Repeat the call with `confirmar=true` to run it."),
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
