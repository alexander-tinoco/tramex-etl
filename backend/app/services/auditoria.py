"""
Audit log.

Records the system's sensitive events in `logs_auditoria`. The case that
justifies its existence is decrypting client credentials: it's the API's
most delicate operation, and without a trace nobody can answer who looked
up which account and when.

Invariant rule: **it records that something was looked up, never what was
obtained.** No entry ever contains passwords, tokens, or cookies.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.models import LogAuditoria, NivelAuditoria, Usuario

logger = logging.getLogger("tramex_api.auditoria")


class Accion:
    """
    Closed vocabulary of auditable actions.

    Declared as constants instead of writing loose strings at each call site
    so the log stays queryable: searching for `CREDENCIAL_CONSULTADA` should
    return every case, not just the ones someone typed without a typo.
    """

    LOGIN_EXITOSO = "login_exitoso"
    LOGIN_FALLIDO = "login_fallido"
    LOGIN_BLOQUEADO = "login_bloqueado"
    LOGOUT = "logout"
    CREDENCIAL_CONSULTADA = "credencial_consultada"
    CREDENCIAL_ILEGIBLE = "credencial_ilegible"
    REGISTRO_CREADO = "registro_creado"
    REGISTRO_ACTUALIZADO = "registro_actualizado"
    REGISTRO_ARCHIVADO = "registro_archivado"
    REGISTRO_RESTAURADO = "registro_restaurado"
    REGISTRO_PURGADO = "registro_purgado"
    ACCESO_DENEGADO = "acceso_denegado"
    USUARIO_CREADO = "usuario_creado"
    CONTRASENA_CAMBIADA = "contrasena_cambiada"


#: Fields that must never appear in an entry's detail.
CAMPOS_PROHIBIDOS = frozenset(
    {"contrasena", "password", "token", "cookie", "authorization", "contrasena_cifrada"}
)


def _sanear(detalle: dict[str, object] | None) -> str | None:
    """
    Serializes the detail, discarding any sensitive field.

    This is a safety net, not an excuse to pass secrets through: if a
    forbidden field makes it this far, it's dropped and logged to the
    application log so the call site gets fixed.
    """
    if not detalle:
        return None
    limpio = {}
    for clave, valor in detalle.items():
        if clave.lower() in CAMPOS_PROHIBIDOS:
            logger.error(
                "Attempted to audit a sensitive field; it was discarded", extra={"campo": clave}
            )
            continue
        limpio[clave] = valor
    if not limpio:
        return None
    return "; ".join(f"{clave}={valor}" for clave, valor in sorted(limpio.items()))


def registrar(
    db: Session,
    *,
    accion: str,
    usuario: Usuario | None = None,
    usuario_correo: str | None = None,
    recurso: str | None = None,
    registro_id: int | None = None,
    cliente_id: int | None = None,
    nivel: NivelAuditoria = NivelAuditoria.INFO,
    request: Request | None = None,
    detalle: dict[str, object] | None = None,
) -> LogAuditoria:
    """
    Records an event in the audit log and also emits it to the structured log.

    It's written to both places on purpose: the table lets the application
    query the history, and the structured log lets alerting fire in the
    aggregator without depending on someone watching the table.
    """
    asiento = LogAuditoria(
        usuario_id=usuario.id if usuario else None,
        usuario_correo=usuario.correo_electronico if usuario else usuario_correo,
        accion=accion,
        recurso=recurso,
        registro_id=registro_id,
        cliente_id=cliente_id,
        nivel=nivel,
        direccion_ip=_ip(request),
        agente_usuario=request.headers.get("user-agent") if request else None,
        detalle=_sanear(detalle),
    )
    db.add(asiento)
    db.commit()
    db.refresh(asiento)

    logger.info(
        "auditoria: %s",
        accion,
        extra={
            "accion": accion,
            "usuario": asiento.usuario_correo,
            "recurso": recurso,
            "registro_id": registro_id,
            "nivel": nivel.value,
        },
    )
    return asiento


def _ip(request: Request | None) -> str | None:
    if request is None:
        return None
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


def consultar(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    accion: str | None = None,
    usuario_id: int | None = None,
    nivel: NivelAuditoria | None = None,
    desde: datetime | None = None,
) -> tuple[list[LogAuditoria], int]:
    """Lists the audit log, most recent first."""
    from sqlalchemy import func

    consulta = select(LogAuditoria)
    if accion:
        consulta = consulta.where(LogAuditoria.accion == accion)
    if usuario_id is not None:
        consulta = consulta.where(LogAuditoria.usuario_id == usuario_id)
    if nivel is not None:
        consulta = consulta.where(LogAuditoria.nivel == nivel)
    if desde is not None:
        consulta = consulta.where(LogAuditoria.ocurrido_en >= desde)

    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    asientos = db.scalars(
        consulta.order_by(LogAuditoria.ocurrido_en.desc(), LogAuditoria.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return list(asientos), total


def purgar_anteriores_a(db: Session, dias: int) -> int:
    """
    Deletes entries older than the retention period.

    It's the only legitimate way for an entry to disappear: the audit log
    doesn't support editing or deleting individual entries, because an
    editable log doesn't hold up as evidence.
    """
    corte = datetime.now(UTC) - timedelta(days=dias)
    # `rowcount` belongs to CursorResult; `execute`'s generic return type
    # doesn't declare it, though for a DELETE it's always there at runtime.
    resultado = cast(
        "CursorResult[Any]",
        db.execute(delete(LogAuditoria).where(LogAuditoria.ocurrido_en < corte)),
    )
    db.commit()
    return resultado.rowcount or 0
