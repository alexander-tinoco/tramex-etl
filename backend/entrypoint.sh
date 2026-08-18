#!/bin/sh
# Punto de entrada de la API.
#
# Deliberadamente NO ejecuta las migraciones. En la version anterior el CMD del
# contenedor hacia `alembic upgrade head && uvicorn ...`, lo que significa que
# con varias replicas todas intentan migrar a la vez sobre la misma base. Las
# migraciones las aplica un job dedicado y de una sola ejecucion (el servicio
# `migraciones` del docker-compose, o un paso previo del despliegue).
#
# Lo que si hace es fallar rapido y con un mensaje claro si el esquema no esta
# al dia, en lugar de arrancar y devolver errores 500 a cada peticion.
set -e

echo "[entrypoint] Verificando que el esquema este al dia..."
if ! python -c "
import sys
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from app.config import settings

configuracion = Config('alembic.ini')
guiones = ScriptDirectory.from_config(configuracion)
esperada = guiones.get_current_head()

motor = create_engine(settings.database_url)
with motor.connect() as conexion:
    actual = MigrationContext.configure(conexion).get_current_revision()

if actual != esperada:
    print(f'[entrypoint] Esquema desfasado: la base esta en {actual!r} y el codigo espera {esperada!r}.')
    print('[entrypoint] Aplica las migraciones antes de arrancar: alembic upgrade head')
    sys.exit(1)
print('[entrypoint] Esquema al dia:', actual)
"; then
    exit 1
fi

exec "$@"
