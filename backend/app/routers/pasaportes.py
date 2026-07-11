"""
Router CRUD para la tabla pasaportes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Pasaporte
from app.schemas import PasaporteBase, PasaporteResponse, PasaporteUpdate

router = APIRouter()


@router.get("/", response_model=list[PasaporteResponse])
def listar(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Listar registros de pasaportes con paginación."""
    return db.query(Pasaporte).offset(skip).limit(limit).all()


@router.get("/{registro_id}", response_model=PasaporteResponse)
def obtener(registro_id: int, db: Session = Depends(get_db)):
    """Obtener un registro por ID."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.post("/", response_model=PasaporteResponse, status_code=201)
def crear(datos: PasaporteBase, db: Session = Depends(get_db)):
    """Crear un nuevo registro de pasaporte."""
    registro = Pasaporte(**datos.model_dump())
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{registro_id}", response_model=PasaporteResponse)
def actualizar(registro_id: int, datos: PasaporteUpdate, db: Session = Depends(get_db)):
    """Actualizar parcialmente un registro."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(registro, campo, valor)

    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db)):
    """Eliminar un registro por ID."""
    registro = db.get(Pasaporte, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(registro)
    db.commit()
