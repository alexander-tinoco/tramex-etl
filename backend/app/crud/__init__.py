"""Repositorios de acceso a datos."""

from app.crud.base import CRUDBase, ErrorDeDescifrado
from app.crud.cliente import crud_cliente
from app.crud.tramites import crud_canada, crud_global, crud_master, crud_pasaporte
from app.crud.usuario import crud_usuario

__all__ = [
    "CRUDBase",
    "ErrorDeDescifrado",
    "crud_canada",
    "crud_cliente",
    "crud_global",
    "crud_master",
    "crud_pasaporte",
    "crud_usuario",
]
