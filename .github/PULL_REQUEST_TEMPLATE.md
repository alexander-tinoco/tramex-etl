## Descripcion del Cambio

Resume que cambia y por que. Enlaza el issue relacionado (ej. "Cierra #12").

## Tipo de Cambio

- [ ] `feat` — nueva funcionalidad
- [ ] `fix` — correccion de un defecto
- [ ] `refactor` — cambio interno sin alterar el comportamiento observable
- [ ] `docs` — solo documentacion
- [ ] `build` / `ci` / `chore` — tooling, dependencias o pipelines

---

## Checklist de Revision

### Calidad
- [ ] `ruff check` y `ruff format --check` pasan sobre `backend/` y `etl/`.
- [ ] `mypy app` no reporta errores nuevos en el backend.
- [ ] `npx tsc --noEmit` compila limpio en el frontend y `npm run lint` no arroja errores.

### Pruebas
- [ ] Los tests del backend pasan y la cobertura sigue por encima del umbral (`--cov-fail-under=85`).
- [ ] Los tests del ETL pasan (`pytest etl/tests/`).
- [ ] Los tests del frontend pasan (`npm test -- --watch=false --browsers=ChromeHeadless`).
- [ ] Se agregaron pruebas para el comportamiento nuevo o para el defecto corregido.

### Datos sensibles y seguridad
- [ ] No se agregaron secretos, `.env` reales, archivos de `raw-data/` ni volcados de base de datos.
- [ ] Los datos usados en tests, capturas y ejemplos son **sinteticos**.
- [ ] Si el cambio lee credenciales descifradas, **escribe el evento en `logs_auditoria`**.
- [ ] Ningun log nuevo imprime contrasenas, tokens ni cookies.

### Contrato y migraciones
- [ ] No se rompio el contrato JSON de los endpoints existentes (o el cambio esta versionado y documentado).
- [ ] Si el esquema cambio, se agrego una migracion de Alembic reversible (`upgrade` **y** `downgrade`).
- [ ] Si cambio el modelo de datos, la autenticacion o el contrato publico, se agrego o actualizo un ADR en `docs/decisions/`.

### Infraestructura
- [ ] `docker compose config` es valido y las imagenes compilan.
- [ ] El `README.md` se actualizo si cambiaron endpoints, variables de entorno o el flujo de arranque.

---

## Evidencia

Adjunta capturas del antes y despues si el cambio afecta al dashboard, o la salida
relevante de consola/logs si afecta al ETL o a la API.
