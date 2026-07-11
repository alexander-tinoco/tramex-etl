"""
Configuración de la aplicación Tramex API.

Carga variables de entorno desde archivos .env usando el mismo patrón
que el ETL: primero busca backend/.env, luego ../etl/.env como fallback.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Carga de variables de entorno (.env)
# ---------------------------------------------------------------------------

# Rutas candidatas: backend/.env (propio) y etl/.env (fallback compartido)
_base_dir = Path(__file__).resolve().parent.parent  # backend/
_env_candidates = [
    _base_dir / ".env",
    _base_dir.parent / "etl" / ".env",
]

for env_path in _env_candidates:
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key_clean = key.strip()
                    if key_clean not in os.environ:
                        os.environ[key_clean] = val.strip().strip("'\"")
        break

# ---------------------------------------------------------------------------
# Variables de configuración
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://postgres:postgres_password@localhost:5434/tramex"
)

FERNET_KEY: str | None = os.environ.get("TRAMEX_FERNET_KEY")

if not FERNET_KEY:
    raise RuntimeError(
        "Falta TRAMEX_FERNET_KEY.  Genera una con generate_key.py o búscala "
        "en el archivo .env e inicialízala antes de arrancar la API."
    )

# Instancia de Fernet lista para cifrar / descifrar contraseñas
fernet = Fernet(FERNET_KEY.encode())
