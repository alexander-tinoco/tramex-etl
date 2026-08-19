# syntax=docker/dockerfile:1
#
# Tramex dashboard image.

# ---------------------------------------------------------------------------
# Dependencies stage
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app
COPY package*.json ./
# `npm ci` installs exactly what's in the lockfile: a reproducible build
# can't depend on npm resolving different versions from one day to the next.
RUN npm ci

# ---------------------------------------------------------------------------
# Development stage: Angular server with hot reload
# ---------------------------------------------------------------------------
FROM deps AS development

COPY . .
EXPOSE 4200
CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--poll", "1000"]

# ---------------------------------------------------------------------------
# Build stage
# ---------------------------------------------------------------------------
FROM deps AS builder

COPY . .
RUN npx ng build --configuration production

# ---------------------------------------------------------------------------
# Production stage: Nginx serving the static files
# ---------------------------------------------------------------------------
FROM nginx:1.31-alpine AS production

# The official image ships the unprivileged `nginx` user, but the master
# process starts as root so it can listen on port 80. It's reconfigured to
# listen on 8080 and run entirely without privileges.
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-seguridad.conf /etc/nginx/snippets/seguridad.conf

# A port above 1024 and every writable path under /tmp, so no step needs
# privileges. The pid path is substituted by pattern rather than by literal
# value because it changes between image versions (/run/nginx.pid in some,
# /var/run/nginx.pid in others).
RUN sed -i 's/listen\s*80;/listen 8080;/' /etc/nginx/conf.d/default.conf \
    && sed -i '/^user /d' /etc/nginx/nginx.conf \
    && sed -i 's#^pid .*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx \
    && chmod -R 777 /tmp

USER nginx
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
