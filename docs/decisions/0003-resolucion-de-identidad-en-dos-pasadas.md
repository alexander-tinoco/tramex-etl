# 0003 · Two-pass identity resolution for people

## Status

Accepted · 2026-07-11

## Context

The source file has four sheets and **no relationship between them**. The
same person shows up in several, written differently each time:

| Sheet | First name | Last name | Passport | Email |
|---|---|---|---|---|
| Master Tramex | `José Ramírez` | — | `G111` | `jose@…` |
| Canada | `José Ramírez` | — | `G111` | — |
| Global entry | `Ana` | `Lopez` | `G222` | `ana@…` |
| Passports | `Ana` | `Lopez` | — | — |

Three problems at once:

1. Some sheets store the full name in one column, others split it into two.
2. Not every sheet captures the same identifiers: **the Passports sheet has
   neither passport number nor email**.
3. The same person is written with varying accents, spacing, and
   capitalization.

When the `clientes` entity was introduced, it had to be decided how to infer
that four rows from four sheets are the same person. The first
implementation used the available fields directly, and in tests against
legacy data it **split José Ramírez into two clients** simply because the
Canada sheet had no email.

## Decision

A person's identity is made of two parts:

```
clave_cliente = SHA256( canonical_name ‖ strong_identifier )
```

- **`nombre_canónico` (canonical name)**: first and last name joined,
  stripped of accents, with whitespace collapsed and lowercased. Makes
  `"José Ramírez"` and `"Ana"/"Lopez"` comparable no matter which sheet they
  come from.
- **`identificador_fuerte` (strong identifier)**: the passport number if it
  exists; if not, the email; if neither exists, an empty string (a *weak*
  key).

On top of that, resolution walks the data **in two passes**:

**First pass — rows with a strong identifier.** These are what define who is
who. Every new key registers a new person.

**Second pass — rows without a strong identifier.** Looked up by canonical
name among people already known:

- If there is **exactly one** match, the row is linked to that person. This
  is the case for the Passports sheet, which would otherwise end up
  disconnected from the rest of that person's record.
- If there are **several** matches (namesakes), a new person is created.

### Why ambiguity is resolved by splitting rather than merging

This is asymmetric on purpose. If two records end up separate and they were
actually the same person, merging them later is trivial. If two records get
merged by mistake, one person's passport has been mixed with another
person's appointment, and **splitting them back apart requires knowing which
row belonged to whom**, information that's already gone by then. On top of
that, in this domain a wrong merge means showing an operator someone else's
credentials.

So when in doubt, the system prefers the recoverable error.

## Consequences

- **People with no hard identifier at all can get split.** Two "Ana Lopez"
  entries with no passport will become two clients. That's the intended
  behavior, but it means the client count is an upper bound on the number of
  real people.
- **Adding a passport to a record changes its natural key.** This is solved
  by recomputing it; assisted merging from the interface is still pending
  automation.
- **The second pass loads active clients into memory.** Acceptable for an
  agency's volume (hundreds of people); at larger scale the canonical name
  would need to be indexed as a generated column.
- **The ETL, the API, and the migration share the same algorithm.** Verified
  with tests at all three entry points.

## Verification

The migration was tested against legacy data with all four sheets: **six
tramite rows resolved into two clients**, including the Passports row with
no strong identifier, which was correctly linked. A dedicated test verifies
that two namesakes with no identifier are **not** merged.
