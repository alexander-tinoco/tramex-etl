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

## Diagramas del Proceso

A continuación se muestran los diagramas explicativos del flujo de datos del ETL:

### 1. Arquitectura General del Sistema
![Arquitectura General](etl/diagramas/Arquitectura%20General%20del%20Sistema.png)

### 2. Flujo de Transformación por Hoja (Detalle del ETL)
![Detalle del ETL](etl/diagramas/Flujo%20de%20Transformación%20por%20Hoja%20%28Detalle%20del%20ETL%29.png)

### 3. Flujo de Cifrado de Datos Sensibles (Secuencia)
![Flujo de Cifrado](etl/diagramas/Flujo%20de%20Cifrado%20de%20Datos%20Sensibles%20%28Secuencia%29.png)

