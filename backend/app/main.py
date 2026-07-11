"""
Punto de entrada de la aplicación FastAPI – Tramex API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import master_tramex, global_entry, pasaportes, canada

# ---------------------------------------------------------------------------
# Instancia de la aplicación
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Tramex API",
    description="API para la gestión de trámites de Tramex",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Middleware CORS (abierto para desarrollo)
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(master_tramex.router, prefix="/api/master-tramex", tags=["Master Tramex"])
app.include_router(global_entry.router, prefix="/api/global-entry", tags=["Global Entry"])
app.include_router(pasaportes.router, prefix="/api/pasaportes", tags=["Pasaportes"])
app.include_router(canada.router, prefix="/api/canada", tags=["Canadá"])


# ---------------------------------------------------------------------------
# Endpoint raíz
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Health-check / bienvenida."""
    return {"status": "ok", "message": "Tramex API v1.0.0"}
