"""
Routers for the four tramite resources.

All are built with the same factory; this module just declares which
repository and which schemas belong to each one.
"""

from app.crud import crud_canada, crud_global, crud_master, crud_pasaporte
from app.routers.factory import crear_router_tramite
from app.schemas import (
    CanadaBase,
    CanadaResponse,
    CanadaUpdate,
    GlobalEntryBase,
    GlobalEntryResponse,
    GlobalEntryUpdate,
    MasterTramexBase,
    MasterTramexResponse,
    MasterTramexUpdate,
    PasaporteBase,
    PasaporteResponse,
    PasaporteUpdate,
)

router_master_tramex = crear_router_tramite(
    crud=crud_master,
    esquema_create=MasterTramexBase,
    esquema_update=MasterTramexUpdate,
    esquema_response=MasterTramexResponse,
    nombre_recurso="Master Tramex",
)

router_global_entry = crear_router_tramite(
    crud=crud_global,
    esquema_create=GlobalEntryBase,
    esquema_update=GlobalEntryUpdate,
    esquema_response=GlobalEntryResponse,
    nombre_recurso="Global Entry",
)

router_pasaportes = crear_router_tramite(
    crud=crud_pasaporte,
    esquema_create=PasaporteBase,
    esquema_update=PasaporteUpdate,
    esquema_response=PasaporteResponse,
    nombre_recurso="Pasaportes",
)

router_canada = crear_router_tramite(
    crud=crud_canada,
    esquema_create=CanadaBase,
    esquema_update=CanadaUpdate,
    esquema_response=CanadaResponse,
    nombre_recurso="Canada",
)
