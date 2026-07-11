"""
Router CRUD para la tabla master_tramex.
Todos los endpoints requieren autenticación JWT (Bearer token).
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import fernet
from app.database import get_db
from app.models import MasterTramex
from app.schemas import MasterTramexBase, MasterTramexResponse, MasterTramexUpdate, PaginatedResponse
from app.security import get_current_user

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
    query = db.query(MasterTramex)
    if buscar:
        query = query.filter(MasterTramex.nombre.ilike(f"%{buscar}%"))
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{registro_id}", response_model=MasterTramexResponse)
def obtener(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Obtener un registro por ID."""
    registro = db.get(MasterTramex, registro_id)
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
    registro = db.get(MasterTramex, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    if not registro.contrasena_cifrada:
        return {"contrasena": None}
    contrasena = fernet.decrypt(registro.contrasena_cifrada.encode()).decode()
    return {"contrasena": contrasena}


@router.post("/", response_model=MasterTramexResponse, status_code=201)
def crear(datos: MasterTramexBase, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Crear un nuevo registro. La contraseña se cifra automáticamente."""
    valores = datos.model_dump(exclude={"contrasena"})
    if datos.contrasena:
        valores["contrasena_cifrada"] = fernet.encrypt(datos.contrasena.encode()).decode()
    registro = MasterTramex(**valores)
    db.add(registro)
    db.commit()
    db.refresh(registro)
    return registro


@router.patch("/{registro_id}", response_model=MasterTramexResponse)
def actualizar(
    registro_id: int,
    datos: MasterTramexUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    """Actualizar parcialmente un registro."""
    registro = db.get(MasterTramex, registro_id)
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
def eliminar(registro_id: int, db: Session = Depends(get_db), _: str = Depends(get_current_user)):
    """Eliminar un registro por ID."""
    registro = db.get(MasterTramex, registro_id)
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    db.delete(registro)
    db.commit()
    return Response(status_code=204)
