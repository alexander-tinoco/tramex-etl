# syntax=docker/dockerfile:1
#
# Imagen de la API de Tramex.
#
# El contexto de build es la RAIZ del repositorio, no ./backend, porque la API
# y el pipeline ETL comparten el paquete `shared/`: las reglas de identidad de
# registros deben ser exactamente las mismas en ambos, y copiar una copia en
# cada imagen crearia dos fuentes de verdad que acabarian divergiendo.
#
#   docker build -f backend/Dockerfile --target production .

# ---------------------------------------------------------------------------
# Etapa base: dependencias del sistema y de Python
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq5 es la biblioteca de PostgreSQL en tiempo de ejecucion; las
# herramientas de compilacion solo hacen falta si pip tuviera que construir
# alguna rueda, y se eliminan en la misma capa para no dejarlas en la imagen.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
COPY shared/ ./shared/

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ./shared \
    && apt-get purge -y --auto-remove build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Etapa de desarrollo: codigo montado como volumen y recarga en caliente
# ---------------------------------------------------------------------------
FROM base AS development

COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Etapa de produccion
# ---------------------------------------------------------------------------
FROM base AS production

# Usuario sin privilegios: si alguien consigue ejecucion dentro del contenedor,
# no debe encontrarse siendo root. La imagen anterior corria como root.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin tramex

COPY --chown=tramex:tramex backend/app ./app
COPY --chown=tramex:tramex backend/alembic ./alembic
COPY --chown=tramex:tramex backend/scripts ./scripts
COPY --chown=tramex:tramex backend/alembic.ini ./alembic.ini
COPY --chown=tramex:tramex backend/entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh

USER tramex

ENV APP_ENV=production
EXPOSE 8000

# La sonda la evalua el orquestador para decidir si enviar trafico a esta
# instancia; consulta la base, no solo el proceso.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
