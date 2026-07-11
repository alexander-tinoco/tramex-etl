"""
Router CRUD para la tabla pasaportes.
Todos los endpoints requieren autenticación JWT (Bearer token).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Pasaporte
from app.schemas import PasaporteBase, PasaporteResponse, PasaporteUpdate, PaginatedResponse
from app.security import get_current_user

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
    query = db.query(Pasaporte)
    if buscar:
        query = query.filter(Pasaporte.nombre.ilike(f"%{buscar}%"))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{registro_id}", response_model=PasaporteResponse)
def obtener(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Obtener un registro por ID."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.post("/", response_model=PasaporteResponse, status_code=201)
def crear(datos: PasaporteBase, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Crear un nuevo registro."""
    registro = Pasaporte(**datos.model_dump())
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{registro_id}", response_model=PasaporteResponse)
def actualizar(
    registro_id: int,
    datos: PasaporteUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Actualizar parcialmente un registro."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(registro, campo, valor)
    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Eliminar un registro por ID."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(registro)
    db.commit()
    return Response(status_code=204)
