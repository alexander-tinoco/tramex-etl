# Architecture Decision Records

A record of the project's underlying technical decisions: what was decided, in
what context, and with what consequences. The goal is that whoever comes along
later — or myself a year from now — doesn't have to reconstruct the reasoning
by reading the code.

Format: **Context** (what real problem existed) → **Decision** (what was done)
→ **Consequences** (what was gained and what was paid) → **Alternatives
discarded**.

| # | Decision | Summary |
|---|---|---|
| [0001](./0001-cifrado-reversible-de-credenciales.md) | Reversible encryption instead of hashing for client credentials | The agency needs to *recover* the client's password, not *verify* it: a hash would make the data useless |
| [0002](./0002-identidad-reproducible-y-carga-idempotente.md) | Reproducible row identity and idempotent loading | Two SHA-256 fingerprints per row enable an upsert that neither duplicates nor overwrites unnecessarily |
| [0003](./0003-resolucion-de-identidad-en-dos-pasadas.md) | Two-pass identity resolution for people | Given ambiguous namesakes, splitting is preferred: merging later is trivial, splitting isn't |
| [0004](./0004-borrado-logico-y-retencion.md) | Soft delete, partial uniqueness, and retention | A partial unique index lets a current record and its archived versions coexist |
| [0005](./0005-autenticacion-roles-y-auditoria.md) | Cookie authentication, roles, and auditing | One user per person is what makes "who looked up that credential?" answerable |
| [0006](./0006-paquete-compartido-entre-etl-y-api.md) | A package shared between the ETL and the API | Three components write to the same tables and must derive identity the same way |
