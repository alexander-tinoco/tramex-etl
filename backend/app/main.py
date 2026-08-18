"""
Punto de entrada de la API de Tramex.

Ensambla la aplicacion FastAPI: observabilidad (logs estructurados y Sentry),
politica de CORS, routers versionados y sondas de salud.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.logging_config import setup_logging
from app.routers import admin, auth, clientes, tramites
from app.security import get_current_user

setup_logging()
logger = logging.getLogger("tramex_api")

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.entorno,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_traces_sample_rate,
        # Los cuerpos de peticion pueden contener contrasenas de clientes.
        send_default_pii=False,
    )
    logger.info("Sentry inicializado", extra={"entorno": settings.entorno})


DESCRIPCION = """
API de gestion de tramites migratorios de la agencia Tramex.

Sustituye la hoja de calculo compartida con la que operaba el equipo: centraliza
clientes y tramites en PostgreSQL, cifra las credenciales de las cuentas de los
clientes con Fernet y deja rastro auditable de cada acceso a datos sensibles.

**Autenticacion.** Todos los recursos de negocio exigen sesion iniciada.
`POST /api/v1/auth/token` deja la sesion en una cookie `httpOnly` (lo que usa el
dashboard) y devuelve tambien el token en el cuerpo, para Swagger, scripts e
integraciones que lo envian en `Authorization: Bearer <token>`.

**Roles.** `operador` gestiona tramites y puede consultar credenciales de
clientes; `admin` ademas administra usuarios, consulta la bitacora de auditoria
y ejecuta la politica de retencion.

**Auditoria.** Cada descifrado de una credencial queda asentado en
`logs_auditoria` con el usuario, la fecha y el registro consultado. Lo que nunca
se registra es la credencial en si.
"""

app = FastAPI(
    title="Tramex API",
    description=DESCRIPCION,
    version=settings.version,
    contact={"name": "Alexander Tinoco", "url": "https://github.com/alexander-tinoco/tramex-etl"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "Salud", "description": "Sondas de disponibilidad y diagnostico."},
        {"name": "Auth", "description": "Emision y verificacion de sesiones."},
        {
            "name": "Administracion",
            "description": (
                "Usuarios, bitacora de auditoria y politica de retencion. Requiere rol `admin`."
            ),
        },
        {"name": "Clientes", "description": "Entidad raiz: personas y sus tramites."},
        {"name": "Master Tramex", "description": "Tramites de visa americana y afines."},
        {"name": "Global Entry", "description": "Tramites de Global Entry."},
        {"name": "Pasaportes", "description": "Citas de expedicion y renovacion de pasaporte."},
        {"name": "Canada", "description": "Tramites con cuenta IRCC."},
    ],
)


@app.middleware("http")
async def registrar_peticiones(request: Request, call_next):
    """Emite una linea de log estructurada por peticion, con su latencia."""
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    duracion = time.perf_counter() - inicio
    logger.info(
        "%s %s -> %s",
        request.method,
        request.url.path,
        respuesta.status_code,
        extra={
            "client": request.client.host if request.client else "desconocido",
            "method": request.method,
            "path": request.url.path,
            "status_code": respuesta.status_code,
            "duration": round(duracion, 4),
        },
    )
    return respuesta


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

#: La autenticacion se declara una sola vez por router en lugar de repetirse en
#: cada endpoint: asi un endpoint nuevo nace protegido por omision, en vez de
#: quedar abierto si alguien olvida la dependencia.
PROTEGIDO = [Depends(get_current_user)]

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(
    admin.router, prefix="/api/v1/admin", tags=["Administracion"], dependencies=PROTEGIDO
)
app.include_router(
    clientes.router, prefix="/api/v1/clientes", tags=["Clientes"], dependencies=PROTEGIDO
)
app.include_router(
    tramites.router_master_tramex,
    prefix="/api/v1/master-tramex",
    tags=["Master Tramex"],
    dependencies=PROTEGIDO,
)
app.include_router(
    tramites.router_global_entry,
    prefix="/api/v1/global-entry",
    tags=["Global Entry"],
    dependencies=PROTEGIDO,
)
app.include_router(
    tramites.router_pasaportes,
    prefix="/api/v1/pasaportes",
    tags=["Pasaportes"],
    dependencies=PROTEGIDO,
)
app.include_router(
    tramites.router_canada, prefix="/api/v1/canada", tags=["Canada"], dependencies=PROTEGIDO
)


# ---------------------------------------------------------------------------
# Salud
# ---------------------------------------------------------------------------


@app.get("/", tags=["Salud"], summary="Identificacion del servicio")
def raiz() -> dict[str, str]:
    """Responde sin tocar la base de datos; util como sonda de vivacidad."""
    return {"status": "ok", "message": f"Tramex API v{settings.version}"}


@app.get("/health", tags=["Salud"], summary="Sonda de disponibilidad")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """
    Sonda de preparacion: verifica que la base de datos responda.

    Devuelve 503 cuando la base no esta disponible, para que el orquestador
    saque la instancia de rotacion en lugar de enviarle trafico que fallara.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Sonda de salud fallida", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La base de datos no esta disponible.",
        ) from exc
    return {"status": "ok", "database": "connected", "version": settings.version}
