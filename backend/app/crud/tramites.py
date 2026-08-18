"""
Repositorios de las cuatro tablas de tramite.

Las cuatro comparten exactamente el mismo comportamiento, que ya vive en
`CRUDBase`; lo unico que cambia entre ellas es el modelo ORM y la definicion de
entidad (que campos identifican la fila y cual es su campo secreto). Por eso
aqui solo se instancian: la version anterior de este modulo repetia el mismo
bloque de cifrado y descifrado cuatro veces.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud.base import CreateSchemaType, CRUDBase, ModelType, UpdateSchemaType
from app.crud.cliente import crud_cliente
from app.models import Canada, GlobalEntry, MasterTramex, Pasaporte
from tramex_shared import CANADA, GLOBAL_ENTRY, MASTER_TRAMEX, PASAPORTES, DefinicionEntidad


class CRUDTramite(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Repositorio de una tabla de tramite, siempre ligada a un cliente."""

    def create(self, db: Session, *, obj_in: CreateSchemaType | dict[str, Any]) -> ModelType:
        """
        Crea el tramite garantizando la integridad referencial.

        Si la peticion no indica `cliente_id`, se resuelve (o se da de alta) el
        cliente a partir de los propios datos del tramite. De este modo la API
        sigue aceptando un alta directa sin obligar a la operadora a conocer el
        identificador interno, pero la fila nunca queda huerfana.
        """
        datos = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
        if not datos.get("cliente_id"):
            datos["cliente_id"] = crud_cliente.resolver_o_crear(db, datos).id
        return super().create(db, obj_in=datos)


def _repositorio(modelo: type, definicion: DefinicionEntidad) -> CRUDTramite[Any, Any, Any]:
    """Fabrica un repositorio de tramite; existe solo para dar nombre al patron."""
    return CRUDTramite(modelo, definicion)


crud_master = _repositorio(MasterTramex, MASTER_TRAMEX)
crud_global = _repositorio(GlobalEntry, GLOBAL_ENTRY)
crud_pasaporte = _repositorio(Pasaporte, PASAPORTES)
crud_canada = _repositorio(Canada, CANADA)
