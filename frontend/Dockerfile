# syntax=docker/dockerfile:1
#
# Imagen del dashboard de Tramex.

# ---------------------------------------------------------------------------
# Etapa de dependencias
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app
COPY package*.json ./
# `npm ci` instala exactamente lo del lockfile: un build reproducible no puede
# depender de que npm resuelva versiones distintas segun el dia.
RUN npm ci

# ---------------------------------------------------------------------------
# Etapa de desarrollo: servidor de Angular con recarga en caliente
# ---------------------------------------------------------------------------
FROM deps AS development

COPY . .
EXPOSE 4200
CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--poll", "1000"]

# ---------------------------------------------------------------------------
# Etapa de compilacion
# ---------------------------------------------------------------------------
FROM deps AS builder

COPY . .
RUN npx ng build --configuration production

# ---------------------------------------------------------------------------
# Etapa de produccion: Nginx sirviendo los estaticos
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS production

# La imagen oficial trae el usuario `nginx` sin privilegios, pero el proceso
# maestro arranca como root para poder escuchar en el 80. Se reconfigura para
# escuchar en el 8080 y correr entero sin privilegios.
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-seguridad.conf /etc/nginx/snippets/seguridad.conf

# Un puerto por encima de 1024 y todas las rutas de escritura bajo /tmp, para
# que ningun paso necesite privilegios. La ruta del pid se sustituye por
# patron y no por valor literal porque cambia entre versiones de la imagen
# (/run/nginx.pid en unas, /var/run/nginx.pid en otras).
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
