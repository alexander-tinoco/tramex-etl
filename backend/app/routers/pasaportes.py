"""
Router CRUD para la tabla pasaportes utilizando la capa CRUD.
Todos los endpoints requieren autenticación JWT (Bearer token).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PasaporteBase, PasaporteResponse, PasaporteUpdate, PaginatedResponse
from app.security import get_current_user
from app.crud.crud_pasaporte import crud_pasaporte

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[PasaporteResponse])
def listar(
    skip: int = 0,
    limit: int = 100,
    buscar: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Listar registros con paginación y búsqueda opcional por nombre."""
    items, total = crud_pasaporte.get_multi(db, skip=skip, limit=limit, buscar=buscar)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{registro_id}", response_model=PasaporteResponse)
def obtener(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Obtener un registro por ID."""
    registro = crud_pasaporte.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.post("/", response_model=PasaporteResponse, status_code=201)
def crear(datos: PasaporteBase, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Crear un nuevo registro."""
    return crud_pasaporte.create(db, obj_in=datos)


@router.patch("/{registro_id}", response_model=PasaporteResponse)
def actualizar(
    registro_id: int,
    datos: PasaporteUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Actualizar parcialmente un registro."""
    registro = crud_pasaporte.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return crud_pasaporte.update(db, db_obj=registro, obj_in=datos)


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Eliminar un registro por ID."""
    registro = crud_pasaporte.remove(db, id=registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return Response(status_code=204)
