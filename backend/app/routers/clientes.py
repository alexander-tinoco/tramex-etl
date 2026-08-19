"""
Client router.

Exposes the model's root entity and, above all, the view the original Excel
never allowed: all of one person's tramites in a single query.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.crud import crud_canada, crud_cliente, crud_global, crud_master, crud_pasaporte
from app.database import get_db
from app.schemas import (
    ClienteCreate,
    ClienteDetalleResponse,
    ClienteResponse,
    ClienteUpdate,
    PaginatedResponse,
)

router = APIRouter()

_REPOSITORIOS_DE_TRAMITE = {
    "master_tramex": crud_master,
    "global_entry": crud_global,
    "pasaportes": crud_pasaporte,
    "canada": crud_canada,
}


def _obtener_o_404(db: Session, cliente_id: int):
    cliente = crud_cliente.get(db, cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No client exists with id {cliente_id}.",
        )
    return cliente


@router.get("/", response_model=PaginatedResponse[ClienteResponse], summary="List clients")
def listar(
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    buscar: Annotated[str | None, Query(description="Partial match on name.")] = None,
):
    items, total = crud_cliente.get_multi(db, skip=skip, limit=limit, buscar=buscar)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get(
    "/{cliente_id}",
    response_model=ClienteDetalleResponse,
    summary="Get a client with a summary of their tramites",
)
def obtener(cliente_id: int, db: Annotated[Session, Depends(get_db)]):
    cliente = _obtener_o_404(db, cliente_id)
    resumen = {
        nombre: repositorio.get_multi(db, cliente_id=cliente_id, limit=1)[1]
        for nombre, repositorio in _REPOSITORIOS_DE_TRAMITE.items()
    }
    return ClienteDetalleResponse(
        **ClienteResponse.model_validate(cliente).model_dump(),
        tramites=resumen,
    )


@router.post(
    "/",
    response_model=ClienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a client",
)
def crear(datos: ClienteCreate, db: Annotated[Session, Depends(get_db)]):
    # `resolver_o_crear` keeps creation idempotent: resubmitting the same
    # client returns the existing one instead of violating the natural-key
    # constraint.
    return crud_cliente.resolver_o_crear(db, datos.model_dump())


@router.patch("/{cliente_id}", response_model=ClienteResponse, summary="Update a client")
def actualizar(cliente_id: int, datos: ClienteUpdate, db: Annotated[Session, Depends(get_db)]):
    cliente = _obtener_o_404(db, cliente_id)
    return crud_cliente.update(db, db_obj=cliente, obj_in=datos)


@router.delete(
    "/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a client and, in cascade, their tramites",
)
def eliminar(cliente_id: int, db: Annotated[Session, Depends(get_db)]):
    cliente = crud_cliente.remove(db, id=cliente_id)
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active client exists with id {cliente_id}.",
        )
    # Archiving the client cascades to their tramites: leaving active
    # tramites hanging off an archived client would produce inconsistent
    # listings.
    for repositorio in _REPOSITORIOS_DE_TRAMITE.values():
        tramites, _ = repositorio.get_multi(db, cliente_id=cliente_id, limit=500)
        for tramite in tramites:
            repositorio.remove(db, id=tramite.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
