# 0002 · Reproducible row identity and idempotent loading

## Status

Accepted · 2026-07-11

## Context

The pipeline's first version loaded data like this:

```python
df.to_sql(table_name, engine, if_exists="append", index=False)
```

With two serious consequences:

1. **Reprocessing the same Excel file duplicated the entire database.** The
   preceding `drop_duplicates()` only deduplicated within the DataFrame,
   never against what was already loaded. And reprocessing is the normal
   case: the sheet gets edited daily and has to be reloaded.
2. **There was no way to know what had changed.** Every run was a blind dump.

Rows in the file carry no identifier of their own: nobody ever assigned an ID
to a tramite. The only thing available is the row's own content.

## Decision

Every row carries two SHA-256 fingerprints computed from its content, each
serving a different purpose:

**`clave_natural`** — a fingerprint of the fields that *identify* the row
(who it is). It has a unique index and is the target of the upsert's
`ON CONFLICT`.

**`hash_fila`** — a fingerprint of *all* the business fields. It lets the
pipeline detect whether anything actually changed.

Loading then becomes:

```sql
INSERT INTO master_tramex (...) VALUES (...)
ON CONFLICT (clave_natural) WHERE eliminado_en IS NULL
DO UPDATE SET ...
WHERE master_tramex.hash_fila IS DISTINCT FROM excluded.hash_fila;
```

Properties this gives us:

- **Idempotency.** Reprocessing the same file duplicates nothing.
- **No useless rewrites.** A row whose content didn't change isn't touched,
  which also avoids re-encrypting credentials that didn't change.
- **Honest reporting.** The pipeline can report how many rows are new, how
  many changed, and how many stayed the same.

### Normalization before fingerprinting

Two entries for the same person must produce the same key. Before hashing,
every value is normalized: accents are stripped (NFKD with diacritics
dropped), internal whitespace is collapsed, edges are trimmed, and the text
is lowercased. That way `"  JOSÉ  Ramírez "` and `"jose ramirez"` converge.

Fields are concatenated with a control separator (`\x1f`) so the
concatenation is injective: without it, `("ab", "c")` and `("a", "bc")` would
produce the same key.

### The hash is computed over plain text, never over the ciphertext

Fernet uses a random IV, so encrypting the same text twice produces different
results. If `hash_fila` included the ciphertext, **every row with a
credential would look modified on every run** and would be rewritten every
time. That's why the hash is computed before encryption. The plaintext
password enters the hash but can't be recovered from it: SHA-256 isn't
reversible.

### A single source of truth

The computation lives in the `shared/tramex_shared` package, imported by the
ETL, the API, and the migrations. If each layer derived the key its own way,
a client entered by hand by an operator and that same client present in the
Excel file would end up as two separate records.

## Consequences

- **Changing `campos_clave` is a data migration.** It alters every existing
  natural key; they all have to be recomputed.
- **The upsert requires PostgreSQL or SQLite.** The pipeline explicitly
  rejects any other dialect rather than silently degrading to a plain
  `append`.
- **There's a per-batch cost:** before writing, the previous state of the
  batch's keys is queried to classify them. That's one extra indexed query
  per batch, in exchange for a reliable report.

## Alternatives discarded

- **`TRUNCATE` and reload.** Would destroy records created via the API and
  the original loading timestamps, and would leave the table empty during
  the load.
- **Comparing rows one by one in Python.** Requires pulling the entire table
  into memory and doesn't use the index.
- **Trusting a key from the file itself** (`ID`, `Cuenta IRCC`). Checked and
  found to repeat, get left blank, and get reused across tramites.
