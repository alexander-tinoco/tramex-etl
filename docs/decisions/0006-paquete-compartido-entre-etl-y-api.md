# 0006 · Un paquete compartido entre el ETL y la API

## Estado

Aceptado · 2026-07-14

## Contexto

Tres componentes escriben en las mismas tablas: el pipeline ETL, la API y las
migraciones de Alembic. Los tres necesitan derivar `clave_natural` y `hash_fila`
exactamente igual (ver [0002](./0002-identidad-reproducible-y-carga-idempotente.md)).

Si cada uno lo implementara por su cuenta, bastaría una diferencia mínima —un
acento sin normalizar, un orden de campos distinto— para que un cliente dado de
alta a mano por una operadora y el mismo cliente presente en el Excel acabaran
como dos registros separados. Y sería un fallo silencioso: nada rompería, solo
aparecerían duplicados que nadie sabría explicar.

## Decisión

Un paquete `shared/tramex_shared` instalable, que contiene las reglas de
identidad y la definición declarativa de las entidades. Lo importan el ETL, la
API y las migraciones.

Consecuencias de empaquetado:

- **La imagen de la API se construye desde la raíz del repositorio**
  (`docker build -f backend/Dockerfile .`), no desde `backend/`, para poder
  copiar `shared/`.
- **No se declara en los `requirements.txt`.** Su ruta relativa cambia según
  desde dónde se instale (la raíz en local, `/app` en la imagen), así que se
  instala como paso aparte: `pip install -e ./shared` en desarrollo,
  `pip install ./shared` en la imagen.

## Qué entra y qué no

Entra solo lo que **debe** ser idéntico en los tres puntos: normalización de
texto, cálculo de las huellas y el catálogo de entidades con sus campos clave.

No entra el esquema de las tablas. Ese lo posee Alembic, y el ETL lo **refleja**
desde la base viva en lugar de redefinirlo. Duplicar las definiciones de tabla
sería exactamente la segunda fuente de verdad que este ADR trata de evitar.

## Alternativas descartadas

- **Copiar el módulo en ambos componentes.** Es el problema, no la solución.
- **Publicarlo en un índice de paquetes privado.** Correcto para equipos que
  despliegan los componentes por separado; aquí añade infraestructura y un paso
  de publicación para un repositorio que se versiona junto.
- **Que el ETL importe del backend.** Acoplaría el pipeline a FastAPI, SQLAlchemy
  y toda la configuración de la API, cuando solo necesita quince líneas de
  funciones puras.
