"""
Factory for the tramite tables' CRUD routers.

The four resources expose the same HTTP surface and only differ in their
repository and schemas. There used to be four files with the same block of
endpoints copy-pasted; here it's generated once and parameterized, so any
contract change (a new filter, one more audit entry) applies to all four by
construction, with none left behind.
"""

# No `from __future__ import annotations`: FastAPI resolves endpoint
# annotations at runtime to build the request model, and here the schemas
# arrive as factory parameters. Deferring them would turn them into strings
# FastAPI couldn't resolve.
import logging
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase, ErrorDeDescifrado
from app.database import get_db
from app.models import NivelAuditoria
from app.schemas import ContrasenaResponse, PaginatedResponse
from app.security import UsuarioActual
from app.services import auditoria, metricas
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
    Builds the complete CRUD router for a tramite resource.

    `nombre_recurso` is used in error messages and in the generated
    documentation, so it doesn't just say "record" in all four cases.
    """
    router = APIRouter()
    tabla = crud.definicion.tabla
    maneja_secreto = crud.definicion.campo_secreto is not None

    def _obtener_o_404(db: Session, registro_id: int, *, incluir_eliminados: bool = False):
        registro = crud.get(db, registro_id, incluir_eliminados=incluir_eliminados)
        if registro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {nombre_recurso} record exists with id {registro_id}.",
            )
        return registro

    @router.get(
        "/",
        response_model=PaginatedResponse[esquema_response],  # type: ignore[valid-type]
        summary=f"List {nombre_recurso}",
    )
    def listar(
        db: Annotated[Session, Depends(get_db)],
        skip: Annotated[int, Query(ge=0, description="Records to skip.")] = 0,
        limit: Annotated[int, Query(ge=1, le=500, description="Page size.")] = 100,
        buscar: Annotated[str | None, Query(description="Partial match on the name.")] = None,
        cliente_id: Annotated[
            int | None, Query(description="Restricts to one client's tramites.")
        ] = None,
        incluir_eliminados: Annotated[
            bool, Query(description="Includes soft-deleted records.")
        ] = False,
        orden: Annotated[
            Literal["id", "reciente"],
            Query(description="`reciente` returns whatever was last modified first."),
        ] = "id",
    ):
        items, total = crud.get_multi(
            db,
            skip=skip,
            limit=limit,
            buscar=buscar,
            cliente_id=cliente_id,
            incluir_eliminados=incluir_eliminados,
            orden=orden,
        )
        return {"total": total, "skip": skip, "limit": limit, "items": items}

    @router.get(
        "/{registro_id}",
        response_model=esquema_response,
        summary=f"Get a {nombre_recurso} record",
    )
    def obtener(registro_id: int, db: Annotated[Session, Depends(get_db)]):
        return _obtener_o_404(db, registro_id)

    @router.post(
        "/",
        response_model=esquema_response,
        status_code=status.HTTP_201_CREATED,
        summary=f"Create a {nombre_recurso} record",
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
        response_model=esquema_response,
        summary=f"Partially update a {nombre_recurso} record",
    )
    def actualizar(
        request: Request,
        registro_id: int,
        datos: esquema_update,  # type: ignore[valid-type]
        db: Annotated[Session, Depends(get_db)],
        usuario: UsuarioActual,
    ):
        registro = _obtener_o_404(db, registro_id)
        # `datos` arrives as the resource's concrete schema; narrowed to
        # BaseModel to read which fields were actually sent.
        campos = sorted(cast(BaseModel, datos).model_dump(exclude_unset=True))
        actualizado = crud.update(db, db_obj=registro, obj_in=datos)
        auditoria.registrar(
            db,
            accion=Accion.REGISTRO_ACTUALIZADO,
            usuario=usuario,
            recurso=tabla,
            registro_id=registro_id,
            cliente_id=getattr(actualizado, "cliente_id", None),
            request=request,
            # Logs the names of the fields touched, never their values: one
            # of them can be the client's credential.
            detalle={"fields": ",".join(campos)},
        )
        return actualizado

    @router.delete(
        "/{registro_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary=f"Archive a {nombre_recurso} record",
        description=(
            "Soft delete: the record stops appearing in listings but is kept "
            "for traceability and can be reactivated. Physical destruction only "
            "happens when the retention policy is applied."
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
                detail=f"No active {nombre_recurso} record exists with id {registro_id}.",
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
        response_model=esquema_response,
        summary=f"Reactivate an archived {nombre_recurso} record",
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
                    f"There is no {nombre_recurso} record with id {registro_id} "
                    "in an archived state."
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
            summary=f"Decrypt the credential of a {nombre_recurso} record",
            description=(
                "Returns the client account's password in the clear. It's the "
                "most sensitive operation in the API and **always** gets logged "
                "in the audit trail, with the user, the date and the record "
                "queried. The password itself is never logged."
            ),
            responses={
                500: {
                    "description": (
                        "The ciphertext could not be decrypted with the active key "
                        "(rotated key, corrupted data, or someone else's backup)."
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
                # Still audited: the access attempt happened, and there's
                # also an infrastructure problem someone needs to address.
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
                metricas.credenciales_consultadas.labels(
                    recurso=tabla, resultado="unreadable"
                ).inc()
                logger.error("Decryption failure", exc_info=exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        "The stored credential could not be decrypted with the "
                        "active key. Check TRAMEX_FERNET_KEY: the key may have "
                        "been rotated, or a backup encrypted with a different one "
                        "was restored."
                    ),
                ) from exc

            metricas.credenciales_consultadas.labels(
                recurso=tabla, resultado="ok" if contrasena else "no_credential"
            ).inc()

            asiento = auditoria.registrar(
                db,
                accion=Accion.CREDENCIAL_CONSULTADA,
                usuario=usuario,
                recurso=tabla,
                registro_id=registro_id,
                cliente_id=getattr(registro, "cliente_id", None),
                nivel=NivelAuditoria.ADVERTENCIA,
                request=request,
                detalle={"had_credential": contrasena is not None},
            )

            return ContrasenaResponse(
                contrasena=contrasena,
                registro_id=registro_id,
                recurso=nombre_recurso,
                auditoria_id=asiento.id,
            )

    return router
