# 0005 · Cookie session authentication, roles, and an audit log

## Status

Accepted · 2026-07-13 · Replaces the environment-variable credential scheme

## Context

The original authentication was:

```python
if form_data.username != API_USERNAME or form_data.password != API_PASSWORD:
    raise HTTPException(status_code=401, ...)
```

Four problems in four lines:

1. **A single shared account.** Impossible to know *who* did what. In a
   system that stores credentials for third parties' government accounts,
   that's exactly the question that needs to be answerable.
2. **Plain-text password** in the process environment.
3. **Comparison with `!=`**, which returns in variable time and leaks
   information through timing.
4. **No attempt limit.** The endpoint was public and passwords could be
   tried indefinitely.

On top of that, the token traveled to the browser and was stored in
`localStorage`, accessible from any script on the page.

## Decision

### Users with bcrypt hashing

A `usuarios` table with bcrypt hashing (cost 12, configurable; tests lower
it to 4 since what's being exercised there is the flow, not the cost). The
password is normalized with SHA-256 and base64 before bcrypt, because
**bcrypt silently truncates at 72 bytes**: without that step, two long
passwords sharing the same prefix would be interchangeable.

Note the contrast with [0001](./0001-cifrado-reversible-de-credenciales.md):
*system users'* passwords are hashed because they only ever need to be
verified; *client account* credentials are encrypted because they need to be
handed back.

When the email doesn't exist, the system still verifies against a decoy
hash, so response timing can't be used to enumerate valid accounts.

### `httpOnly` cookie session

The JWT travels in an `httpOnly` cookie, invisible to JavaScript: an XSS
alone is no longer enough to steal the session. `Authorization: Bearer` is
still accepted because Swagger, scripts, and integrations don't use cookies.

The design consequence is that **the frontend can't read its own session**,
so it asks the API on startup (`GET /auth/me`). That's more work than
reading `localStorage`, and it's the right price to pay.

Every request revalidates that the user still exists and is active: a JWT
stays cryptographically valid even after someone has been deactivated.

### Two roles

`operador` handles tramites and looks up client credentials; `admin`
additionally manages users, reads the audit log, and runs retention. Only
two, because the real team is made up of two roles; adding more without a
need for them produces a permissions matrix nobody maintains.

The system prevents demoting or deactivating the last active administrator:
recovering from that would require editing the database by hand.

### Audit log

`logs_auditoria` records logins (successful, failed, and locked out),
creations, edits, archiving, restores, purges, and above all, **every
decryption of a client credential**, with user, date, IP, and the record
looked up. The endpoint's response returns the identifier of the entry it
just wrote, and the interface shows it: whoever looked something up sees
that it was logged.

The rule is invariable: **what was looked up is logged, never what was
obtained.** A sanitizer strips any sensitive field that reaches the log
detail by mistake and leaves a note in the application log so the call site
gets fixed.

### Brute-force protection

Account lockout after N failures in a window (resists IP rotation), plus a
per-origin limit (slows down sweeping many accounts). Counters live in Redis
so multiple replicas share state; without Redis there's an in-memory
fallback, which is why the configuration **requires Redis in production**.

The window doesn't extend with each attempt: if it did, a persistent
attacker could keep a legitimate account locked out indefinitely.

## Consequences

- **Cold start.** Creating users requires being authenticated, so there's an
  idempotent script that seeds the first administrator. In development it
  generates and prints a password; in production it requires one, because a
  password printed in container logs is a leaked password.
- **A proxy is needed in development.** The cookie doesn't travel between
  `localhost:4200` and `localhost:8000`; the Angular dev server forwards
  `/api` so there's a single origin.
- **Tests don't mock authentication.** Test clients actually sign in against
  the real endpoint; replacing it with an override would leave the most
  sensitive part uncovered.

## Out of scope

No MFA, no automatic `API_SECRET_KEY` rotation, no password expiration, no
email-based recovery. These become necessary if the system is exposed to the
open internet; today it's designed for the agency's own network behind
HTTPS.
