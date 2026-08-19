# syntax=docker/dockerfile:1
#
# Tramex API image.
#
# The build context is the repository ROOT, not ./backend, because the API
# and the ETL pipeline share the `shared/` package: record identity rules
# must be exactly the same in both, and copying a duplicate into each image
# would create two sources of truth that would eventually drift apart.
#
#   docker build -f backend/Dockerfile --target production .

# ---------------------------------------------------------------------------
# Base stage: system and Python dependencies
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libpq5 is the PostgreSQL runtime library; the build tools are only needed
# if pip has to build a wheel, and they're removed in the same layer so they
# don't stay in the image.
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
# Development stage: code mounted as a volume, hot reload
# ---------------------------------------------------------------------------
FROM base AS development

COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------------------------------------------------------------------
# Production stage
# ---------------------------------------------------------------------------
FROM base AS production

# Unprivileged user: if someone manages to get execution inside the
# container, they shouldn't find themselves as root. The previous image ran
# as root.
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

# The orchestrator evaluates the probe to decide whether to send traffic to
# this instance; it queries the database, not just the process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
