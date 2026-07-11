"""
Punto de entrada de la aplicación FastAPI – Tramex API.
"""

import logging
import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import sentry_sdk

from app.config import settings
from app.database import get_db
from app.routers import master_tramex, global_entry, pasaportes, canada, auth
from app.logging_config import setup_logging

# Inicializar logging estructurado JSON
setup_logging()
logger = logging.getLogger("tramex_api")

# Inicializar Sentry si el DSN está configurado
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("Sentry initialized successfully.")

# ---------------------------------------------------------------------------
# Instancia de la aplicación
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Tramex API",
    description="API para la gestión de trámites de Tramex",
    version="1.0.0",
)

# Middleware de Logging de Peticiones
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"Request processed: {request.method} {request.url.path} -> {response.status_code}",
        extra={
            "client": request.client.host if request.client else "unknown",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration": round(duration, 4),
        }
    )
    return response

# ---------------------------------------------------------------------------
# Middleware CORS (abierto para desarrollo)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router,          prefix="/api/v1/auth",          tags=["Auth"])
app.include_router(master_tramex.router, prefix="/api/v1/master-tramex", tags=["Master Tramex"])
app.include_router(global_entry.router,  prefix="/api/v1/global-entry",  tags=["Global Entry"])
app.include_router(pasaportes.router,    prefix="/api/v1/pasaportes",    tags=["Pasaportes"])
app.include_router(canada.router,        prefix="/api/v1/canada",        tags=["Canadá"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    """Bienvenida – no requiere autenticación."""
    return {"status": "ok", "message": "Tramex API v1.0.0"}


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    """
    Health check extendido: verifica la conectividad con la base de datos.
    Retorna HTTP 200 si la BD está disponible, HTTP 503 si no lo está.
    """
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Base de datos no disponible: {exc}")
