from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models import GlobalEntry
from app.schemas import GlobalEntryBase, GlobalEntryUpdate
from app.config import fernet


class CRUDGlobalEntry(CRUDBase[GlobalEntry, GlobalEntryBase, GlobalEntryUpdate]):
    """Repositores CRUD con lógica específica para trámites de Global Entry."""

    def create(self, db: Session, *, obj_in: GlobalEntryBase) -> GlobalEntry:
        """Crea el registro, cifrando la contraseña si es proveída."""
        obj_in_data = obj_in.model_dump()
        contrasena = obj_in_data.pop("contrasena", None)
        if contrasena:
            obj_in_data["contrasena_cifrada"] = fernet.encrypt(contrasena.encode()).decode()
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self, db: Session, *, db_obj: GlobalEntry, obj_in: GlobalEntryUpdate | dict
    ) -> GlobalEntry:
        """Actualiza el registro, cifrando la nueva contraseña si es proveída."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)

        contrasena = update_data.pop("contrasena", None)
        if contrasena:
            update_data["contrasena_cifrada"] = fernet.encrypt(contrasena.encode()).decode()

        return super().update(db, db_obj=db_obj, obj_in=update_data)

    def decrypt_password(self, db_obj: GlobalEntry) -> str | None:
        """Descifra de forma segura la contraseña cifrada almacenada."""
        if not db_obj.contrasena_cifrada:
            return None
        try:
            return fernet.decrypt(db_obj.contrasena_cifrada.encode()).decode()
        except Exception:
            return None


crud_global = CRUDGlobalEntry(GlobalEntry)
