## Description of the Change

Summarize what changes and why. Link the related issue (e.g. "Closes #12").

## Type of Change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `refactor` — internal change with no observable behavior change
- [ ] `docs` — documentation only
- [ ] `build` / `ci` / `chore` — tooling, dependencies or pipelines

---

## Review Checklist

### Quality
- [ ] `ruff check` and `ruff format --check` pass on `backend/` and `etl/`.
- [ ] `mypy app` reports no new errors in the backend.
- [ ] `npx tsc --noEmit` compiles clean on the frontend and `npm run lint` reports no errors.

### Tests
- [ ] Backend tests pass and coverage stays above the threshold (`--cov-fail-under=85`).
- [ ] ETL tests pass (`pytest etl/tests/`).
- [ ] Frontend tests pass (`npm test -- --watch=false --browsers=ChromeHeadless`).
- [ ] Tests were added for the new behavior or the fixed bug.

### Sensitive data and security
- [ ] No secrets, real `.env` files, `raw-data/` files or database dumps were added.
- [ ] Data used in tests, screenshots and examples is **synthetic**.
- [ ] If the change reads decrypted credentials, **it writes the event to `logs_auditoria`**.
- [ ] No new log prints passwords, tokens or cookies.

### Contract and migrations
- [ ] The JSON contract of existing endpoints wasn't broken (or the change is versioned and documented).
- [ ] If the schema changed, a reversible Alembic migration was added (`upgrade` **and** `downgrade`).
- [ ] If the data model, authentication or public contract changed, an ADR was added or updated in `docs/decisions/`.

### Infrastructure
- [ ] `docker compose config` is valid and the images build.
- [ ] `README.md` was updated if endpoints, environment variables or the startup flow changed.

---

## Evidence

Attach before/after screenshots if the change affects the dashboard, or the
relevant console/log output if it affects the ETL or the API.
