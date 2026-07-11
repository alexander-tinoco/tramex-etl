"""
Punto de entrada de la aplicación FastAPI – Tramex API.
"""

import logging
import time
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import master_tramex, global_entry, pasaportes, canada, auth

# ---------------------------------------------------------------------------
# Configuración del Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tramex_api")

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
        f"Client={request.client.host if request.client else 'unknown'} "
        f"Method={request.method} Path={request.url.path} "
        f"Status={response.status_code} Duration={duration:.4f}s"
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

app.include_router(auth.router,          prefix="/api/auth",          tags=["Auth"])
app.include_router(master_tramex.router, prefix="/api/master-tramex", tags=["Master Tramex"])
app.include_router(global_entry.router,  prefix="/api/global-entry",  tags=["Global Entry"])
app.include_router(pasaportes.router,    prefix="/api/pasaportes",    tags=["Pasaportes"])
app.include_router(canada.router,        prefix="/api/canada",        tags=["Canadá"])


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
