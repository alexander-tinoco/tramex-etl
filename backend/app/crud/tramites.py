"""
Repositories for the four tramite tables.

All four share exactly the same behavior, which already lives in `CRUDBase`;
the only thing that changes between them is the ORM model and the entity
definition (which fields identify the row and which is its secret field). So
here they're just instantiated: the previous version of this module repeated
the same encryption/decryption block four times over.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud.base import CreateSchemaType, CRUDBase, ModelType, UpdateSchemaType
from app.crud.cliente import crud_cliente
from app.models import Canada, GlobalEntry, MasterTramex, Pasaporte
from tramex_shared import CANADA, GLOBAL_ENTRY, MASTER_TRAMEX, PASAPORTES, DefinicionEntidad


class CRUDTramite(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Repository for a tramite table, always linked to a client."""

    def create(self, db: Session, *, obj_in: CreateSchemaType | dict[str, Any]) -> ModelType:
        """
        Creates the tramite while guaranteeing referential integrity.

        If the request doesn't specify `cliente_id`, the client is resolved
        (or created) from the tramite's own data. This way the API keeps
        accepting a direct creation without forcing the operator to know the
        internal identifier, while the row never ends up orphaned.
        """
        datos = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
        if not datos.get("cliente_id"):
            datos["cliente_id"] = crud_cliente.resolver_o_crear(db, datos).id
        return super().create(db, obj_in=datos)


def _repositorio(modelo: type, definicion: DefinicionEntidad) -> CRUDTramite[Any, Any, Any]:
    """Builds a tramite repository; exists only to give the pattern a name."""
    return CRUDTramite(modelo, definicion)


crud_master = _repositorio(MasterTramex, MASTER_TRAMEX)
crud_global = _repositorio(GlobalEntry, GLOBAL_ENTRY)
crud_pasaporte = _repositorio(Pasaporte, PASAPORTES)
crud_canada = _repositorio(Canada, CANADA)
