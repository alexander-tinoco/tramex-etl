"""
Entry point of the Tramex API.

Assembles the FastAPI application: observability (structured logs and
Sentry), CORS policy, versioned routers and health probes.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.logging_config import setup_logging
from app.routers import admin, auth, clientes, tramites
from app.security import get_current_user
from app.services import metricas

setup_logging()
logger = logging.getLogger("tramex_api")

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.entorno,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_traces_sample_rate,
        # Request bodies can contain client passwords.
        send_default_pii=False,
    )
    logger.info("Sentry initialized", extra={"entorno": settings.entorno})


DESCRIPCION = """
Tramex agency immigration tramite management API.

Replaces the shared spreadsheet the team used to operate from: centralizes
clients and tramites in PostgreSQL, encrypts client account credentials with
Fernet, and leaves an auditable trail of every access to sensitive data.

**Authentication.** Every business resource requires an active session.
`POST /api/v1/auth/token` leaves the session in an `httpOnly` cookie (what the
dashboard uses) and also returns the token in the body, for Swagger, scripts
and integrations that send it as `Authorization: Bearer <token>`.

**Roles.** `operador` manages tramites and can look up client credentials;
`admin` additionally manages users, browses the audit log, and runs the
retention policy.

**Auditing.** Every time a credential is decrypted, it's recorded in
`logs_auditoria` with the user, the date and the record that was looked up.
What's never logged is the credential itself.
"""

app = FastAPI(
    title="Tramex API",
    description=DESCRIPCION,
    version=settings.version,
    contact={"name": "Alexander Tinoco", "url": "https://github.com/alexander-tinoco/tramex-etl"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "Salud", "description": "Availability and diagnostic probes."},
        {"name": "Auth", "description": "Session issuance and verification."},
        {
            "name": "Administracion",
            "description": ("Users, audit log, and retention policy. Requires the `admin` role."),
        },
        {"name": "Clientes", "description": "Root entity: people and their tramites."},
        {"name": "Master Tramex", "description": "US visa tramites and related processes."},
        {"name": "Global Entry", "description": "Global Entry tramites."},
        {"name": "Pasaportes", "description": "Passport issuance and renewal appointments."},
        {"name": "Canada", "description": "Tramites with an IRCC account."},
    ],
)


#: Headers that harden the browser's behavior. The API responds with JSON,
#: not HTML, but the dashboard consumes it from the same origin through the
#: reverse proxy, and a misinterpreted error response can still execute.
CABECERAS_DE_SEGURIDAD = {
    # Stops the browser from guessing the content type and treating a JSON
    # response as if it were HTML or a script.
    "X-Content-Type-Options": "nosniff",
    # No API response should load inside a frame: this is the clickjacking
    # defense.
    "X-Frame-Options": "DENY",
    # Don't leak the full URL (which carries record identifiers) to sites
    # external to the browser when navigating away from here.
    "Referrer-Policy": "no-referrer",
    # The API needs no camera, microphone, or geolocation.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    # Nothing from the API should execute or be embedded as a document.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}

#: Routes that return their own HTML instead of JSON: the interactive
#: documentation. Swagger UI and ReDoc load their assets from a CDN, so the
#: locked-down policy above would leave them blank. They get their own,
#: still-restrictive policy, instead of relaxing the one for the whole API.
RUTAS_DE_DOCUMENTACION = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})

CSP_DOCUMENTACION = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


@app.middleware("http")
async def observar_peticiones(request: Request, call_next):
    """
    Emits a structured log entry, feeds the metrics, and adds the headers.

    All three concerns live in the same middleware because all three need to
    wrap the entire request; splitting them into three layers would only add
    hops.
    """
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    duracion = time.perf_counter() - inicio

    # The route template ("/api/v1/canada/{registro_id}"), not the concrete
    # URL: otherwise every record in the database would generate its own series.
    ruta = metricas.normalizar_ruta(request.url.path, request.scope.get("path_params") or {})

    metricas.peticiones_totales.labels(
        metodo=request.method, ruta=ruta, codigo=str(respuesta.status_code)
    ).inc()
    metricas.duracion_peticiones.labels(metodo=request.method, ruta=ruta).observe(duracion)

    for cabecera, valor in CABECERAS_DE_SEGURIDAD.items():
        respuesta.headers.setdefault(cabecera, valor)
    if request.url.path in RUTAS_DE_DOCUMENTACION:
        respuesta.headers["Content-Security-Policy"] = CSP_DOCUMENTACION
    if settings.entorno == "production":
        # Production only: locally, work happens over http, and this header
        # would leave the browser forcing https against a server that doesn't speak it.
        respuesta.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )

    logger.info(
        "%s %s -> %s",
        request.method,
        request.url.path,
        respuesta.status_code,
        extra={
            "client": request.client.host if request.client else "unknown",
            "method": request.method,
            "path": request.url.path,
            "route": ruta,
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

#: Authentication is declared once per router instead of repeated on every
#: endpoint: that way a new endpoint is born protected by default, instead of
#: staying open if someone forgets the dependency.
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
# Health
# ---------------------------------------------------------------------------


@app.get("/", tags=["Salud"], summary="Service identification")
def raiz() -> dict[str, str]:
    """Responds without touching the database; useful as a liveness probe."""
    return {"status": "ok", "message": f"Tramex API v{settings.version}"}


@app.get("/health", tags=["Salud"], summary="Availability probe")
def health(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """
    Readiness probe: checks that the database responds.

    Returns 503 when the database is unavailable, so the orchestrator pulls
    the instance out of rotation instead of sending it traffic that will fail.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("Health probe failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is not available.",
        ) from exc
    return {"status": "ok", "database": "connected", "version": settings.version}


@app.get(
    "/metrics",
    tags=["Salud"],
    summary="Metrics in Prometheus format",
    include_in_schema=False,
)
def metricas_prometheus() -> Response:
    """
    Exposes the application's counters and histograms.

    Doesn't require a session because Prometheus scrapes without credentials,
    but it doesn't reveal data either: these are aggregates with no client
    identifiers. In a real deployment this port shouldn't be published
    outside the internal network.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
