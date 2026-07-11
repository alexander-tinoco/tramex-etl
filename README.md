# Tramex System

Sistema integral para la gestión y procesamiento de datos de Tramex.

## Estructura del Proyecto

- `/etl`: Scripts y esquemas para la extracción, transformación y carga (ETL) de los datos en crudo.
- `/backend`: API y lógica de negocio.
- `/frontend`: Aplicación web para el usuario final.
- `/pgadmin`: Configuración de pgAdmin para administrar la base de datos.
- `/raw-data`: Archivos en crudo (ej. Excel) ignorados por git.

## Desarrollo

### Base de Datos
Puedes levantar la base de datos PostgreSQL y pgAdmin usando Docker:
```bash
docker compose up -d
```

- **Base de datos**: `localhost:5434`
- **pgAdmin**: `http://localhost:5051` (Usuario: `admin@admin.com` / Contraseña: `admin_password`)

### ETL
Los archivos de ETL se encuentran en la carpeta `/etl`. El script carga automáticamente la configuración desde el archivo `etl/.env`.

Para ejecutar el ETL:
1. Asegúrate de tener el entorno virtual activo:
   ```bash
   source .venv/bin/activate
   ```
2. Ejecuta el script apuntando al archivo Excel deseado:
   ```bash
   python etl/etl_tramex.py raw-data/TRAMEX.xlsx
   ```

### Backend (API)
El backend es una API REST construida con **FastAPI** que reemplaza el flujo de trabajo basado en Excel. Se encuentra en la carpeta `/backend`.

Para levantar el servidor de desarrollo:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- **API**: `http://localhost:8000` (o el puerto que prefieras, por ejemplo `8001` si el 8000 está ocupado)
- **Documentación interactiva (Swagger)**: `http://localhost:8000/docs`
- **Documentación alternativa (ReDoc)**: `http://localhost:8000/redoc`

#### Endpoints disponibles

| Recurso | Prefijo | Operaciones |
|---|---|---|
| Autenticación | `/api/auth/token` | POST (Público: requiere `username` y `password` en formato form-data) |
| Master Tramex | `/api/master-tramex/` | GET, POST, PATCH, DELETE |
| Global Entry | `/api/global-entry/` | GET, POST, PATCH, DELETE |
| Pasaportes | `/api/pasaportes/` | GET, POST, PATCH, DELETE |
| Canadá | `/api/canada/` | GET, POST, PATCH, DELETE |

> **Nota de contraseñas**: Para los recursos de **Master Tramex**, **Global Entry** y **Canadá**, la contraseña original se puede descifrar consumiendo el endpoint protected `GET {prefijo}/{id}/password`.

#### Autenticación y Seguridad

La API se encuentra protegida con autenticación basada en tokens JWT.
1. **Iniciar Sesión:** Envía una solicitud `POST /api/auth/token` con los campos `username` y `password` en el cuerpo del formulario (OAuth2 password request).
2. **Consumo de Endpoints:** Adjunta el token recibido en la cabecera `Authorization` de cada solicitud:
   ```http
   Authorization: Bearer <access_token>
   ```

Los parámetros de autenticación se configuran en el archivo `backend/.env` mediante:
* `API_SECRET_KEY`: Frase secreta utilizada para la firma de tokens JWT.
* `API_USERNAME`: Usuario administrador (por defecto `admin`).
* `API_PASSWORD`: Contraseña de administrador (por defecto `changeme`).

> **Nota de endpoints `GET /`**: Todos los endpoints de listado (`GET`) soportan los siguientes parámetros de consulta (query params) opcionales:
> * `buscar`: Filtra los registros cuyo campo `nombre` coincida parcialmente (búsqueda insensible a mayúsculas/minúsculas).
> * `skip`: Número de registros a omitir (por defecto `0`).
> * `limit`: Número máximo de registros a retornar (por defecto `100`).

> **Nota de seguridad de datos**: Las contraseñas se cifran automáticamente con Fernet (AES-128) en la base de datos al crear (POST) o actualizar parcialmente (PATCH) los registros, y nunca se devuelven en los listados generales.

### CI/CD (GitHub Actions)
El proyecto incluye un flujo de integración continua (CI) mediante **GitHub Actions** en `.github/workflows/ci.yml`.

Este flujo se dispara automáticamente en cada `push` o `pull_request` a las ramas `main` o `master` y realiza:
1. **Pruebas del Backend**: Instala las dependencias y ejecuta el conjunto de tests con reporte de cobertura (`pytest --cov=app`).
2. **Validación Sintáctica del ETL**: Valida que el script de python de ETL compile correctamente.


## Diagramas del Proceso

A continuación se muestran los diagramas explicativos del flujo de datos del ETL:

### 1. Arquitectura General del Sistema
![Arquitectura General](etl/diagramas/Arquitectura%20General%20del%20Sistema.png)

### 2. Flujo de Transformación por Hoja (Detalle del ETL)
![Detalle del ETL](etl/diagramas/Flujo%20de%20Transformación%20por%20Hoja%20%28Detalle%20del%20ETL%29.png)

### 3. Flujo de Cifrado de Datos Sensibles (Secuencia)
![Flujo de Cifrado](etl/diagramas/Flujo%20de%20Cifrado%20de%20Datos%20Sensibles%20%28Secuencia%29.png)

---

## Diagramas del Backend

A continuación se muestran los diagramas explicativos del funcionamiento del Backend:

### 1. Arquitectura del Backend
![Arquitectura del Backend](backend/diagramas/Arquitectura%20del%20Backend.png)

### 2. Flujo de Autenticación JWT (Secuencia)
![Autenticación JWT](backend/diagramas/Flujo%20de%20Autenticación%20JWT%20%28Secuencia%29.png)

### 3. Flujo de Descifrado Seguro de Contraseñas (Secuencia)
![Descifrado Seguro](backend/diagramas/Flujo%20de%20Descifrado%20Seguro%20de%20Contraseñas%20%28Secuencia%29.png)


