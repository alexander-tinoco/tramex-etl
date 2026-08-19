# 0004 · Soft delete, partial uniqueness, and retention policy

## Status

Accepted · 2026-07-12

## Context

`DELETE /api/v1/{resource}/{id}` used to destroy the row outright. In a
system that holds personal data — names, phone numbers, emails, passport
numbers, and account credentials — that creates two problems: an accidental
deletion is unrecoverable, and an archive action leaves no trace of who did
it or when.

At the same time, keeping personal data forever isn't right either.

## Decision

### Soft delete

Every business table has `eliminado_en`. The API's `DELETE` marks the row
instead of destroying it; it stops showing up in listings but stays
available with `?incluir_eliminados=true` and can be reactivated with
`POST /{id}/restaurar`. Both the archive action and the restore are logged
in the audit trail.

### Partial uniqueness

The interesting technical consequence: if `clave_natural` were plain
`UNIQUE`, an archived row would **still occupy its key** and would block
re-inserting the good version of that same identity. The constraint is
therefore a **partial** unique index:

```sql
CREATE UNIQUE INDEX uq_master_tramex_clave_natural_activa
    ON master_tramex (clave_natural) WHERE eliminado_en IS NULL;
```

That way, one current record and any number of archived versions of the same
identity can coexist. The ETL's `ON CONFLICT` targets this index.

This also solved a real problem that surfaced during migration: the
previous `append`-only loading had left duplicate rows in the database. The
migration detects them by natural key, **keeps the oldest one and archives
the rest** instead of destroying them, and only then enforces uniqueness.

### Retention

`POST /api/v1/admin/retencion/ejecutar` permanently destroys anything
archived more than `DIAS_RETENCION` days ago (365 by default) and any audit
entries outside that window. It requires the `admin` role, requires an
explicit `confirmar=true`, and is logged at `ALERTA` level.

It's the system's only irreversible operation.

### The audit log allows no soft delete

`logs_auditoria` deliberately has no `eliminado_en` and no edit endpoint: an
audit log that can be corrected isn't an audit log. The only legitimate way
for an entry to disappear is age-based purging.

## Consequences

- **Every query filters by `eliminado_en IS NULL`.** This is centralized in
  `CRUDBase`, so a new repository inherits it automatically; forgetting it
  would expose archived records.
- **Composite indexes `(cliente_id, eliminado_en)`** on all four tables, so
  the filter doesn't degrade per-client queries.
- **The database grows more.** At an agency's volume that's irrelevant next
  to the traceability it buys.
- **Archiving a client cascades to their tramites.** Leaving active tramites
  hanging off an archived client would produce inconsistent listings.
- **The purge has to actually run.** Today it's manual; a scheduled job is
  the natural next step, still pending.

## Alternatives discarded

- **A separate history table.** Duplicates the schema and forces two
  structures to be kept in sync.
- **Full versioning** (temporal-tables style). Answers "what did this row
  look like on such-and-such date," a question nobody asks in this domain,
  in exchange for considerable complexity.
