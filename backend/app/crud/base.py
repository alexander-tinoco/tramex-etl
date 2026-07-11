from typing import Any, Generic, List, Type, TypeVar, Tuple
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import Base

# Definición de tipos genéricos para modelos y esquemas
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Clase base con operaciones CRUD genéricas (Create, Read, Update, Delete).
    Reduce la duplicación de código en la capa de endpoints/controladores.
    """

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> ModelType | None:
        """Obtiene un único registro por su ID primary key."""
        return db.scalar(select(self.model).where(self.model.id == id))

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100, buscar: str | None = None
    ) -> Tuple[List[ModelType], int]:
        """
        Retorna una lista paginada de registros y el conteo total.
        Soporta búsquedas insensibles a mayúsculas/minúsculas por el campo 'nombre'.
        """
        query = select(self.model)
        if buscar:
            query = query.where(self.model.nombre.ilike(f"%{buscar}%"))
        
        # Conteo de registros total coincidente
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        
        # Paginación y ejecución
        stmt = query.offset(skip).limit(limit)
        items = db.scalars(stmt).all()
        
        return list(items), total

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """Crea un nuevo registro a partir del esquema de entrada."""
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]
    ) -> ModelType:
        """Actualiza parcialmente un registro existente (PATCH)."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> ModelType | None:
        """Elimina físicamente un registro por su ID."""
        obj = db.scalar(select(self.model).where(self.model.id == id))
        if obj:
            db.delete(obj)
            db.commit()
        return obj
