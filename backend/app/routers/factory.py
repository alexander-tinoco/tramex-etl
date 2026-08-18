"""
Fabrica de routers CRUD para las tablas de tramite.

Los cuatro recursos exponen exactamente la misma superficie HTTP y solo
difieren en su repositorio y sus esquemas. Antes existian cuatro archivos con
el mismo bloque de endpoints copiado; aqui se genera una sola vez y se
parametriza, de modo que cualquier cambio de contrato (un filtro nuevo, un
codigo de estado distinto) se aplica a los cuatro por construccion.
"""

# Sin `from __future__ import annotations`: FastAPI resuelve las anotaciones de
# los endpoints en tiempo de ejecucion para construir el modelo de la peticion,
# y aqui los esquemas llegan como parametros de la fabrica. Diferirlas las
# convertiria en cadenas que FastAPI no podria resolver.
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.database import get_db
from app.schemas import ContrasenaResponse, PaginatedResponse


def crear_router_tramite(
    *,
    crud: CRUDBase[Any, Any, Any],
    esquema_create: type[BaseModel],
    esquema_update: type[BaseModel],
    esquema_response: type[BaseModel],
    nombre_recurso: str,
) -> APIRouter:
    """
    Construye el router CRUD completo de un recurso de tramite.

    `nombre_recurso` se usa en los mensajes de error y en la descripcion de los
    endpoints, para que la documentacion generada no diga "registro" en los
    cuatro casos.
    """
    router = APIRouter()
    maneja_secreto = crud.definicion.campo_secreto is not None

    def _obtener_o_404(db: Session, registro_id: int, *, incluir_eliminados: bool = False):
        registro = crud.get(db, registro_id, incluir_eliminados=incluir_eliminados)
        if registro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe un registro de {nombre_recurso} con id {registro_id}.",
            )
        return registro

    @router.get(
        "/",
        response_model=PaginatedResponse[esquema_response],  # type: ignore[valid-type]
        summary=f"Listar {nombre_recurso}",
    )
    def listar(
        db: Annotated[Session, Depends(get_db)],
        skip: Annotated[int, Query(ge=0, description="Registros a omitir.")] = 0,
        limit: Annotated[int, Query(ge=1, le=500, description="Tamano de pagina.")] = 100,
        buscar: Annotated[
            str | None, Query(description="Coincidencia parcial sobre el nombre.")
        ] = None,
        cliente_id: Annotated[
            int | None, Query(description="Restringe a los tramites de un cliente.")
        ] = None,
        incluir_eliminados: Annotated[
            bool, Query(description="Incluye los registros dados de baja logicamente.")
        ] = False,
    ):
        items, total = crud.get_multi(
            db,
            skip=skip,
            limit=limit,
            buscar=buscar,
            cliente_id=cliente_id,
            incluir_eliminados=incluir_eliminados,
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @router.get(
        "/{registro_id}",
        response_model=esquema_response,  # type: ignore[valid-type]
        summary=f"Obtener un registro de {nombre_recurso}",
    )
    def obtener(registro_id: int, db: Annotated[Session, Depends(get_db)]):
        return _obtener_o_404(db, registro_id)

    @router.post(
        "/",
        response_model=esquema_response,  # type: ignore[valid-type]
        status_code=status.HTTP_201_CREATED,
        summary=f"Crear un registro de {nombre_recurso}",
    )
    def crear(datos: esquema_create, db: Annotated[Session, Depends(get_db)]):  # type: ignore[valid-type]
        return crud.create(db, obj_in=datos)

    @router.patch(
        "/{registro_id}",
        response_model=esquema_response,  # type: ignore[valid-type]
        summary=f"Actualizar parcialmente un registro de {nombre_recurso}",
    )
    def actualizar(
        registro_id: int,
        datos: esquema_update,  # type: ignore[valid-type]
        db: Annotated[Session, Depends(get_db)],
    ):
        registro = _obtener_o_404(db, registro_id)
        return crud.update(db, db_obj=registro, obj_in=datos)

    @router.delete(
        "/{registro_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary=f"Dar de baja un registro de {nombre_recurso}",
        description=(
            "Borrado logico: el registro deja de aparecer en los listados pero se "
            "conserva para trazabilidad y puede reactivarse. La destruccion fisica "
            "la realiza el proceso de retencion."
        ),
    )
    def eliminar(registro_id: int, db: Annotated[Session, Depends(get_db)]):
        if crud.remove(db, id=registro_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe un registro activo de {nombre_recurso} con id {registro_id}.",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{registro_id}/restaurar",
        response_model=esquema_response,  # type: ignore[valid-type]
        summary=f"Reactivar un registro de {nombre_recurso} dado de baja",
    )
    def restaurar(registro_id: int, db: Annotated[Session, Depends(get_db)]):
        registro = crud.restore(db, id=registro_id)
        if registro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No hay un registro de {nombre_recurso} con id {registro_id} "
                    "en estado dado de baja."
                ),
            )
        return registro

    if maneja_secreto:

        @router.get(
            "/{registro_id}/password",
            response_model=ContrasenaResponse,
            summary=f"Descifrar la credencial de un registro de {nombre_recurso}",
            description=(
                "Devuelve la contrasena en claro de la cuenta del cliente. Es la "
                "operacion mas sensible de la API."
            ),
        )
        def obtener_contrasena(registro_id: int, db: Annotated[Session, Depends(get_db)]):
            registro = _obtener_o_404(db, registro_id, incluir_eliminados=True)
            contrasena = crud.descifrar_secreto(registro)
            return ContrasenaResponse(
                contrasena=contrasena,
                registro_id=registro_id,
                recurso=nombre_recurso,
            )

    return router
