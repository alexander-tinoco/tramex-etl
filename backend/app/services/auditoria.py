"""
Bitacora de auditoria.

Registra los eventos sensibles del sistema en `logs_auditoria`. El caso que
justifica su existencia es el descifrado de credenciales de clientes: es la
operacion mas delicada de la API y, sin rastro, nadie puede responder quien
consulto que cuenta y cuando.

Regla invariable: **se registra que se consulto, nunca que se obtuvo.** Ningun
asiento contiene contrasenas, tokens ni cookies.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import LogAuditoria, NivelAuditoria, Usuario

logger = logging.getLogger("tramex_api.auditoria")


class Accion:
    """
    Vocabulario cerrado de acciones auditables.

    Se declara como constantes en lugar de escribir cadenas sueltas en cada
    llamada para que la bitacora sea consultable: buscar por
    `CREDENCIAL_CONSULTADA` debe devolver todos los casos, no los que alguien
    escribio sin errata.
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


#: Campos que jamas deben aparecer en el detalle de un asiento.
CAMPOS_PROHIBIDOS = frozenset(
    {"contrasena", "password", "token", "cookie", "authorization", "contrasena_cifrada"}
)


def _sanear(detalle: dict[str, object] | None) -> str | None:
    """
    Serializa el detalle descartando cualquier campo sensible.

    Es una red de seguridad, no una excusa para pasar secretos: si un campo
    prohibido llega hasta aqui, se descarta y se deja constancia en el log de
    aplicacion para que se corrija el punto de llamada.
    """
    if not detalle:
        return None
    limpio = {}
    for clave, valor in detalle.items():
        if clave.lower() in CAMPOS_PROHIBIDOS:
            logger.error(
                "Se intento auditar un campo sensible; fue descartado", extra={"campo": clave}
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
    Asienta un evento en la bitacora y lo emite tambien al log estructurado.

    Se escribe en los dos sitios a proposito: la tabla permite consultar el
    historial desde la aplicacion, y el log estructurado permite alertar en el
    agregador sin depender de que alguien mire la tabla.
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
    """Lista la bitacora, de lo mas reciente a lo mas antiguo."""
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
    Elimina asientos mas antiguos que el periodo de retencion.

    Es la unica forma legitima de que desaparezca un asiento: la bitacora no
    admite edicion ni borrado individual, porque una bitacora corregible no
    sirve como evidencia.
    """
    corte = datetime.now(UTC) - timedelta(days=dias)
    resultado = db.execute(delete(LogAuditoria).where(LogAuditoria.ocurrido_en < corte))
    db.commit()
    return resultado.rowcount or 0
