# Guia de Contribucion

Gracias por tu interes en colaborar con **Tramex**. Este documento describe el flujo de
trabajo, las convenciones de codigo y los controles de calidad que el repositorio aplica
de forma automatica.

---

## 1. Flujo de Trabajo

1. **Haz un fork** del repositorio.
2. **Crea una rama** partiendo de `main`, nombrada segun el tipo de cambio:
   ```bash
   git checkout -b feat/auditoria-de-accesos
   git checkout -b fix/etl-fechas-invalidas
   ```
3. **Desarrolla y verifica en local** ejecutando linters y tests del modulo que tocaste.
4. **Haz commits limpios** siguiendo *Conventional Commits* (seccion 3).
5. **Abre un Pull Request** contra `main` usando la plantilla del repositorio.

---

## 2. Convenciones de Codigo

### ETL y Backend (Python)

- Sigue **PEP 8** con un ancho maximo de 100 columnas; `ruff format` es la fuente de verdad.
- Las transformaciones del ETL deben ser **funciones puras** sin efectos secundarios, para
  que sean testeables sin base de datos ni archivos.
- Usa **anotaciones de tipo** en toda firma publica. `mypy` corre en CI en modo no estricto
  pero con `--warn-unused-ignores`.
- Respeta la separacion de capas del backend:
  **Router** (mapeo HTTP) -> **CRUD/Repositorio** (acceso a datos) -> **Modelo** (ORM).
  La logica de negocio no vive en los routers.
- Nunca registres credenciales, tokens ni contrasenas descifradas en los logs.

Antes de commitear:

```bash
cd backend
.venv/bin/python -m ruff check app ../etl
.venv/bin/python -m ruff format --check app ../etl
.venv/bin/python -m mypy app
.venv/bin/python -m pytest --cov=app --cov-fail-under=85
```

### Frontend (Angular / TypeScript)

- **TypeScript estricto.** El uso de `any` esta prohibido por ESLint; modela la respuesta
  del backend en `src/app/models/`.
- Los componentes son **standalone** y usan **signals** para el estado local.
  Evita `BehaviorSubject` para estado sincrono de UI.
- Un componente que supere ~200 lineas debe dividirse. La logica compartida vive en
  servicios (`src/app/services/`), no duplicada entre componentes.

Antes de commitear:

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm test -- --watch=false --browsers=ChromeHeadless
```

---

## 3. Convenciones de Commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/es/). `commitlint`
valida cada mensaje mediante el hook `commit-msg` de Husky.

```text
<tipo>(<alcance>): <descripcion corta en minusculas, imperativo>

[cuerpo opcional]
```

**Tipos permitidos:** `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`,
`chore`, `style`, `revert`.

**Alcances permitidos:** `etl`, `backend`, `frontend`, `db`, `api`, `auth`, `security`,
`infra`, `docker`, `ci`, `docs`, `deps`, `release`.

Ejemplos validos:

```text
feat(etl): make loading idempotent with natural key upsert
fix(security): stop silencing fernet decryption failures
docs: rewrite readme with architecture and er diagrams
```

---

## 4. Controles Automaticos

| Control | Herramienta | Cuando corre |
|---|---|---|
| Formato del mensaje de commit | `commitlint` | Hook `commit-msg` |
| Lint y formato de archivos staged | `lint-staged` + `ruff` + `eslint` | Hook `pre-commit` |
| Escaneo de secretos | `gitleaks` | CI, en cada push y PR |
| Tests del ETL | `pytest` | CI |
| Tests y cobertura del backend | `pytest --cov-fail-under=85` | CI |
| Lint, tipos y tests del frontend | `eslint`, `tsc`, `karma` | CI |
| Build de imagenes Docker | `docker/build-push-action` | CD, en tags `v*` |
| Actualizacion de dependencias | `dependabot` | Semanal |

Instala los hooks una sola vez tras clonar:

```bash
npm install
```

---

## 5. Decisiones de Arquitectura

Cualquier cambio que altere el modelo de datos, el esquema de autenticacion o el
contrato publico de la API debe acompanarse de un **ADR** en `docs/decisions/`,
siguiendo el formato de los existentes (`Contexto` / `Decision` / `Consecuencias`).
Si la nueva decision reemplaza a una previa, marca la anterior como `Reemplazada por`.

---

## 6. Datos Sensibles

Este proyecto maneja datos personales reales (pasaportes, telefonos, correos y
credenciales de cuentas de clientes). Por lo tanto:

- **Nunca** subas archivos de `raw-data/`, volcados de base de datos ni `.env` reales.
- Usa siempre datos sinteticos en tests, capturas de pantalla y ejemplos de documentacion.
- Toda funcionalidad nueva que lea credenciales descifradas **debe** escribir en
  `logs_auditoria`. Un PR que acceda a datos sensibles sin auditarlos sera rechazado.
