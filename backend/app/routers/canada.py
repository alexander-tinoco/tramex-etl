"""
Router CRUD para la tabla canada utilizando la capa CRUD.
Todos los endpoints requieren autenticación JWT (Bearer token).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CanadaBase, CanadaResponse, CanadaUpdate, PaginatedResponse
from app.security import get_current_user
from app.crud.crud_canada import crud_canada

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[CanadaResponse])
def listar(
    skip: int = 0,
    limit: int = 100,
    buscar: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Listar registros con paginación y búsqueda opcional por nombre."""
    items, total = crud_canada.get_multi(db, skip=skip, limit=limit, buscar=buscar)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{registro_id}", response_model=CanadaResponse)
def obtener(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Obtener un registro por ID."""
    registro = crud_canada.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.get("/{registro_id}/password")
def obtener_contrasena(
    registro_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Descifrar y retornar la contraseña de un registro."""
    registro = crud_canada.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    contrasena = crud_canada.decrypt_password(registro)
    return {"contrasena": contrasena}


@router.post("/", response_model=CanadaResponse, status_code=201)
def crear(datos: CanadaBase, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Crear un nuevo registro."""
    return crud_canada.create(db, obj_in=datos)


@router.patch("/{registro_id}", response_model=CanadaResponse)
def actualizar(
    registro_id: int,
    datos: CanadaUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Actualizar parcialmente un registro."""
    registro = crud_canada.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return crud_canada.update(db, db_obj=registro, obj_in=datos)


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Eliminar un registro por ID."""
    registro = crud_canada.remove(db, id=registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return Response(status_code=204)
