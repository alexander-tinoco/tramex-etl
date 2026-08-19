# Contributing Guide

Thanks for your interest in contributing to **Tramex**. This document describes the
workflow, code conventions, and quality gates the repository enforces automatically.

---

## 1. Workflow

1. **Fork** the repository.
2. **Create a branch** off `main`, named after the type of change:
   ```bash
   git checkout -b feat/access-audit-log
   git checkout -b fix/etl-invalid-dates
   ```
3. **Develop and verify locally** by running the linters and tests for the module you touched.
4. **Make clean commits** following *Conventional Commits* (section 3).
5. **Open a Pull Request** against `main` using the repository's template.

---

## 2. Code Conventions

### ETL and Backend (Python)

- Follow **PEP 8** with a maximum line width of 100 columns; `ruff format` is the source of truth.
- ETL transformations must be **pure functions** with no side effects, so they can
  be tested without a database or files.
- Use **type annotations** on every public signature. `mypy` runs in CI in non-strict
  mode but with `--warn-unused-ignores`.
- Respect the backend's layer separation:
  **Router** (HTTP mapping) -> **CRUD/Repository** (data access) -> **Model** (ORM).
  Business logic does not live in the routers.
- Never log credentials, tokens, or decrypted passwords.

Before committing:

```bash
cd backend
.venv/bin/python -m ruff check app ../etl
.venv/bin/python -m ruff format --check app ../etl
.venv/bin/python -m mypy app
.venv/bin/python -m pytest --cov=app --cov-fail-under=85
```

### Frontend (Angular / TypeScript)

- **Strict TypeScript.** Using `any` is forbidden by ESLint; model the backend's
  response shape in `src/app/models/`.
- Components are **standalone** and use **signals** for local state.
  Avoid `BehaviorSubject` for synchronous UI state.
- A component that grows past ~200 lines should be split. Shared logic lives in
  services (`src/app/services/`), not duplicated across components.

Before committing:

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm test -- --watch=false --browsers=ChromeHeadless
```

---

## 3. Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/). `commitlint`
validates every message via Husky's `commit-msg` hook.

```text
<type>(<scope>): <short description, lowercase, imperative>

[optional body]
```

**Allowed types:** `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`,
`chore`, `style`, `revert`.

**Allowed scopes:** `etl`, `backend`, `frontend`, `db`, `api`, `auth`, `security`,
`infra`, `docker`, `ci`, `docs`, `deps`, `release`.

Valid examples:

```text
feat(etl): make loading idempotent with natural key upsert
fix(security): stop silencing fernet decryption failures
docs: rewrite readme with architecture and er diagrams
```

---

## 4. Automated Checks

| Check | Tool | When it runs |
|---|---|---|
| Commit message format | `commitlint` | `commit-msg` hook |
| Lint and format of staged files | `lint-staged` + `ruff` + `eslint` | `pre-commit` hook |
| Secret scanning | `gitleaks` | CI, on every push and PR |
| ETL tests | `pytest` | CI |
| Backend tests and coverage | `pytest --cov-fail-under=85` | CI |
| Frontend lint, types, and tests | `eslint`, `tsc`, `karma` | CI |
| Docker image build | `docker/build-push-action` | CD, on `v*` tags |
| Dependency updates | `dependabot` | Weekly |

Install the hooks once after cloning:

```bash
npm install
```

---

## 5. Architecture Decisions

Any change that alters the data model, the authentication scheme, or the public
API contract must be accompanied by an **ADR** in `docs/decisions/`, following
the format of the existing ones (`Context` / `Decision` / `Consequences`). If the
new decision replaces a previous one, mark the previous one as `Superseded by`.

---

## 6. Sensitive Data

This project handles real personal data (passports, phone numbers, emails, and
client account credentials). Therefore:

- **Never** upload files from `raw-data/`, database dumps, or real `.env` files.
- Always use synthetic data in tests, screenshots, and documentation examples.
- Any new functionality that reads decrypted credentials **must** write to
  `logs_auditoria`. A PR that accesses sensitive data without auditing it will be rejected.
