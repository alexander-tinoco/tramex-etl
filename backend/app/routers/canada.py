"""
Router CRUD para la tabla canada.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import fernet
from app.database import get_db
from app.models import Canada
from app.schemas import CanadaBase, CanadaResponse, CanadaUpdate

router = APIRouter()


@router.get("/", response_model=list[CanadaResponse])
def listar(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Listar registros de canada con paginación."""
    return db.query(Canada).offset(skip).limit(limit).all()


@router.get("/{registro_id}", response_model=CanadaResponse)
def obtener(registro_id: int, db: Session = Depends(get_db)):
    """Obtener un registro por ID."""
    registro = db.get(Canada, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    return registro


@router.post("/", response_model=CanadaResponse, status_code=201)
def crear(datos: CanadaBase, db: Session = Depends(get_db)):
    """Crear un nuevo registro. La contraseña se cifra automáticamente."""
    valores = datos.model_dump(exclude={"contrasena"})
    if datos.contrasena:
        valores["contrasena_cifrada"] = fernet.encrypt(datos.contrasena.encode()).decode()
    registro = Canada(**valores)
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{registro_id}", response_model=CanadaResponse)
def actualizar(registro_id: int, datos: CanadaUpdate, db: Session = Depends(get_db)):
    """Actualizar parcialmente un registro."""
    registro = db.get(Canada, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")

    cambios = datos.model_dump(exclude_unset=True, exclude={"contrasena"})
    if datos.contrasena is not None:
        cambios["contrasena_cifrada"] = fernet.encrypt(datos.contrasena.encode()).decode()

    for campo, valor in cambios.items():
        setattr(registro, campo, valor)

    db.commit()
    db.refresh(registro)
    return registro


@router.delete("/{registro_id}", status_code=204)
def eliminar(registro_id: int, db: Session = Depends(get_db)):
    """Eliminar un registro por ID."""
    registro = db.get(Canada, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(registro)
    db.commit()
