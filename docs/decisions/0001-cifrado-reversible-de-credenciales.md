# 0001 · Reversible encryption (Fernet) instead of hashing for client credentials

## Status

Accepted · 2026-07-10

## Context

The agency manages immigration tramites on behalf of its clients. To do that
it needs to **log into those clients' accounts**: the consular portal, the
Global Entry account, Canada's IRCC account. The passwords for those accounts
were sitting in cells of a shared Excel file, in plain text, next to the
person's name and passport number.

The instinctive reaction to "we need to store passwords" is *hash them with
bcrypt*. Here that would be a category error.

## Decision

Client credentials are **encrypted reversibly** with Fernet (AES-128 in CBC
mode with HMAC-SHA256 for authentication), not hashed.

The reason is that hashing and encryption solve different problems:

| | Hash (bcrypt) | Encryption (Fernet) |
|---|---|---|
| Question it answers | "is this the correct password?" | "what was the password?" |
| Reversible | No, by design | Yes, with the key |
| Use case | **Verifying** whoever authenticates | **Custodying** someone else's secret |

The agency doesn't need to *verify* the client's password: it needs to
*recover* it to type into the corresponding portal. A hash is irreversible by
definition, so it would make the data useless.

That's why both mechanisms coexist in the same system, and it's important not
to confuse them:

- **System users' passwords** (operators and administrators): bcrypt hash.
  The system only ever needs to verify them. See [0005](./0005-autenticacion-roles-y-auditoria.md).
- **Client account credentials**: Fernet encryption. The system needs to
  hand them back.

### Operational consequences

1. **The key is the critical asset.** Whoever has `TRAMEX_FERNET_KEY` and a
   database dump has every credential. The key must live in a secrets
   manager, never alongside the database backup.
2. **Rotating the key requires re-encrypting.** Changing the variable alone
   isn't enough: everything has to be decrypted with the old key and
   re-encrypted with the new one. Automating this is still pending.
3. **Every decryption is audited.** Because the data is recoverable, the
   control can't be cryptographic and has to be access-based: every lookup
   is logged in `logs_auditoria` with user, date, IP, and record.
4. **A decryption failure surfaces loudly.** If a ciphertext exists but
   doesn't open with the active key, `ErrorDeDescifrado` is raised and the
   API responds with a 500. The previous version returned `None`,
   indistinguishable from "this record has no password": client credentials
   were being lost silently.

### Why Fernet instead of hand-rolled AES

Fernet defaults to everything that's easy to get wrong implementing AES
directly: a random IV per message, HMAC authentication (protects against
tampering with the ciphertext), and a timestamp. It's a closed construction,
with no parameters to misconfigure.

Its non-deterministic nature has one consequence for the pipeline: encrypting
the same text twice produces different ciphertexts, so **ciphertexts can't be
compared to detect changes**. That's why `hash_fila` is computed over the
normalized plain text and never over the ciphertext. See
[0002](./0002-identidad-reproducible-y-carga-idempotente.md).

## Alternatives discarded

- **bcrypt hash.** Would make the data unrecoverable and useless for the operation.
- **An external password manager** (Bitwarden, 1Password) with the API only
  storing references. That's the right call at larger scale, and it removes
  the custody of the secret altogether, but it adds a paid external
  dependency and a point of failure for a small agency. It's the natural
  next step if the system grows.
- **Column-level encryption in PostgreSQL** (`pgcrypto`). Moves the key into
  the database, which is exactly where it shouldn't be: a compromised dump
  would then include everything needed to decrypt.
