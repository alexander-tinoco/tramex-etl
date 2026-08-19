# 0006 · A package shared between the ETL and the API

## Status

Accepted · 2026-07-14

## Context

Three components write to the same tables: the ETL pipeline, the API, and
the Alembic migrations. All three need to derive `clave_natural` and
`hash_fila` in exactly the same way (see
[0002](./0002-identidad-reproducible-y-carga-idempotente.md)).

If each one implemented it independently, the smallest difference — an
un-normalized accent, a different field order — would be enough for a client
entered by hand by an operator and that same client present in the Excel
file to end up as two separate records. And it would fail silently: nothing
would break, duplicates would just show up that nobody could explain.

## Decision

An installable `shared/tramex_shared` package holds the identity rules and
the declarative definition of the entities. It's imported by the ETL, the
API, and the migrations.

Packaging consequences:

- **The API image is built from the repository root**
  (`docker build -f backend/Dockerfile .`), not from `backend/`, so that
  `shared/` can be copied in.
- **It isn't declared in `requirements.txt`.** Its relative path changes
  depending on where it's installed from (the repo root locally, `/app` in
  the image), so it's installed as a separate step: `pip install -e ./shared`
  in development, `pip install ./shared` in the image.

## What's in and what isn't

Only what **must** be identical across all three points goes in: text
normalization, fingerprint computation, and the entity catalog with its key
fields.

The table schema doesn't go in. Alembic owns that, and the ETL **reflects**
it from the live database instead of redefining it. Duplicating table
definitions would be exactly the second source of truth this ADR is trying
to avoid.

## Alternatives discarded

- **Copying the module into both components.** That's the problem, not the solution.
- **Publishing it to a private package index.** Right for teams that deploy
  their components separately; here it adds infrastructure and a publishing
  step for a repository that's versioned as a whole.
- **Having the ETL import from the backend.** Would couple the pipeline to
  FastAPI, SQLAlchemy, and the whole API configuration, when it only needs
  fifteen lines of pure functions.
