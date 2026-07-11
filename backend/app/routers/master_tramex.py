"""
Router CRUD para la tabla master_tramex utilizando la capa CRUD.
Todos los endpoints requieren autenticación JWT (Bearer token).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import MasterTramexBase, MasterTramexResponse, MasterTramexUpdate, PaginatedResponse
from app.security import get_current_user
from app.crud.crud_master import crud_master

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[MasterTramexResponse])
def listar(
    skip: int = 0,
    limit: int = 100,
    buscar: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Listar registros con paginación y búsqueda opcional por nombre."""
    items, total = crud_master.get_multi(db, skip=skip, limit=limit, buscar=buscar)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{registro_id}", response_model=MasterTramexResponse)
def obtener(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Obtener un registro por ID."""
    registro = crud_master.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.get("/{registro_id}/password")
def obtener_contrasena(
    registro_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Descifrar y retornar la contraseña de un registro (solo usuarios autenticados)."""
    registro = crud_master.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    contrasena = crud_master.decrypt_password(registro)
    return {"contrasena": contrasena}


@router.post("/", response_model=MasterTramexResponse, status_code=201)
def crear(datos: MasterTramexBase, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Crear un nuevo registro. La contraseña se cifra automáticamente."""
    return crud_master.create(db, obj_in=datos)


@router.patch("/{registro_id}", response_model=MasterTramexResponse)
def actualizar(
    registro_id: int,
    datos: MasterTramexUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Actualizar parcialmente un registro."""
    registro = crud_master.get(db, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return crud_master.update(db, db_obj=registro, obj_in=datos)


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Eliminar un registro por ID."""
    registro = crud_master.remove(db, id=registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return Response(status_code=204)
