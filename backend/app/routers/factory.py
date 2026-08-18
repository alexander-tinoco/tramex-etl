"""
Fabrica de routers CRUD para las tablas de tramite.

Los cuatro recursos exponen la misma superficie HTTP y solo difieren en su
repositorio y sus esquemas. Antes existian cuatro archivos con el mismo bloque
de endpoints copiado; aqui se genera una sola vez y se parametriza, de modo que
cualquier cambio de contrato (un filtro nuevo, un asiento de auditoria mas) se
aplica a los cuatro por construccion, sin que ninguno se quede atras.
"""

# Sin `from __future__ import annotations`: FastAPI resuelve las anotaciones de
# los endpoints en tiempo de ejecucion para construir el modelo de la peticion,
# y aqui los esquemas llegan como parametros de la fabrica. Diferirlas las
# convertiria en cadenas que FastAPI no podria resolver.
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase, ErrorDeDescifrado
from app.database import get_db
from app.models import NivelAuditoria
from app.schemas import ContrasenaResponse, PaginatedResponse
from app.security import UsuarioActual
from app.services import auditoria
from app.services.auditoria import Accion

logger = logging.getLogger("tramex_api.tramites")


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

    `nombre_recurso` se usa en los mensajes de error y en la documentacion
    generada, para que no diga "registro" en los cuatro casos.
    """
    router = APIRouter()
    tabla = crud.definicion.tabla
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
    def crear(
        request: Request,
        datos: esquema_create,  # type: ignore[valid-type]
        db: Annotated[Session, Depends(get_db)],
        usuario: UsuarioActual,
    ):
        registro = crud.create(db, obj_in=datos)
        auditoria.registrar(
            db,
            accion=Accion.REGISTRO_CREADO,
            usuario=usuario,
            recurso=tabla,
            registro_id=registro.id,
            cliente_id=getattr(registro, "cliente_id", None),
            request=request,
        )
        return registro

    @router.patch(
        "/{registro_id}",
        response_model=esquema_response,  # type: ignore[valid-type]
        summary=f"Actualizar parcialmente un registro de {nombre_recurso}",
    )
    def actualizar(
        request: Request,
        registro_id: int,
        datos: esquema_update,  # type: ignore[valid-type]
        db: Annotated[Session, Depends(get_db)],
        usuario: UsuarioActual,
    ):
        registro = _obtener_o_404(db, registro_id)
        campos = sorted(datos.model_dump(exclude_unset=True))
        actualizado = crud.update(db, db_obj=registro, obj_in=datos)
        auditoria.registrar(
            db,
            accion=Accion.REGISTRO_ACTUALIZADO,
            usuario=usuario,
            recurso=tabla,
            registro_id=registro_id,
            cliente_id=getattr(actualizado, "cliente_id", None),
            request=request,
            # Se registran los nombres de los campos tocados, nunca sus valores:
            # uno de ellos puede ser la credencial del cliente.
            detalle={"campos": ",".join(campos)},
        )
        return actualizado

    @router.delete(
        "/{registro_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary=f"Dar de baja un registro de {nombre_recurso}",
        description=(
            "Borrado logico: el registro deja de aparecer en los listados pero se "
            "conserva para trazabilidad y puede reactivarse. La destruccion fisica "
            "solo ocurre al aplicar la politica de retencion."
        ),
    )
    def eliminar(
        request: Request,
        registro_id: int,
        db: Annotated[Session, Depends(get_db)],
        usuario: UsuarioActual,
    ):
        registro = crud.remove(db, id=registro_id)
        if registro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe un registro activo de {nombre_recurso} con id {registro_id}.",
            )
        auditoria.registrar(
            db,
            accion=Accion.REGISTRO_ARCHIVADO,
            usuario=usuario,
            recurso=tabla,
            registro_id=registro_id,
            cliente_id=getattr(registro, "cliente_id", None),
            request=request,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{registro_id}/restaurar",
        response_model=esquema_response,  # type: ignore[valid-type]
        summary=f"Reactivar un registro de {nombre_recurso} dado de baja",
    )
    def restaurar(
        request: Request,
        registro_id: int,
        db: Annotated[Session, Depends(get_db)],
        usuario: UsuarioActual,
    ):
        registro = crud.restore(db, id=registro_id)
        if registro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No hay un registro de {nombre_recurso} con id {registro_id} "
                    "en estado dado de baja."
                ),
            )
        auditoria.registrar(
            db,
            accion=Accion.REGISTRO_RESTAURADO,
            usuario=usuario,
            recurso=tabla,
            registro_id=registro_id,
            cliente_id=getattr(registro, "cliente_id", None),
            request=request,
        )
        return registro

    if maneja_secreto:

        @router.get(
            "/{registro_id}/password",
            response_model=ContrasenaResponse,
            summary=f"Descifrar la credencial de un registro de {nombre_recurso}",
            description=(
                "Devuelve la contrasena en claro de la cuenta del cliente. Es la "
                "operacion mas sensible de la API y **siempre** queda asentada en "
                "la bitacora de auditoria, con el usuario, la fecha y el registro "
                "consultado. La contrasena en si jamas se registra."
            ),
            responses={
                500: {
                    "description": (
                        "El criptograma no pudo descifrarse con la llave activa "
                        "(llave rotada, dato corrupto o respaldo ajeno)."
                    )
                }
            },
        )
        def obtener_contrasena(
            request: Request,
            registro_id: int,
            db: Annotated[Session, Depends(get_db)],
            usuario: UsuarioActual,
        ):
            registro = _obtener_o_404(db, registro_id, incluir_eliminados=True)

            try:
                contrasena = crud.descifrar_secreto(registro)
            except ErrorDeDescifrado as exc:
                # Se audita igual: el intento de acceso ocurrio, y ademas hay un
                # problema de infraestructura que alguien debe atender.
                auditoria.registrar(
                    db,
                    accion=Accion.CREDENCIAL_ILEGIBLE,
                    usuario=usuario,
                    recurso=tabla,
                    registro_id=registro_id,
                    cliente_id=getattr(registro, "cliente_id", None),
                    nivel=NivelAuditoria.ALERTA,
                    request=request,
                )
                logger.error("Fallo de descifrado", exc_info=exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "La credencial almacenada no pudo descifrarse con la llave "
                        "activa. Revisa TRAMEX_FERNET_KEY: puede haberse rotado la "
                        "llave o restaurado un respaldo cifrado con otra."
                    ),
                ) from exc

            asiento = auditoria.registrar(
                db,
                accion=Accion.CREDENCIAL_CONSULTADA,
                usuario=usuario,
                recurso=tabla,
                registro_id=registro_id,
                cliente_id=getattr(registro, "cliente_id", None),
                nivel=NivelAuditoria.ADVERTENCIA,
                request=request,
                detalle={"tenia_credencial": contrasena is not None},
            )

            return ContrasenaResponse(
                contrasena=contrasena,
                registro_id=registro_id,
                recurso=nombre_recurso,
                auditoria_id=asiento.id,
            )

    return router
