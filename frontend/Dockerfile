# Stage 1: Construcción de la aplicación Angular
FROM node:22-alpine AS builder

WORKDIR /app

# Copiar archivos de dependencias e instalar
COPY package*.json ./
RUN npm ci

# Copiar el código fuente y compilar para producción
COPY . .
RUN npx ng build --configuration production

# Stage 2: Servir los archivos con Nginx
FROM nginx:alpine

# Copiar los archivos compilados del constructor de Angular al directorio raíz de Nginx
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Copiar la configuración personalizada de Nginx para el Reverse Proxy
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
