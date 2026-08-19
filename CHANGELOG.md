# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
versioning adheres to [Semantic Versioning](https://semver.org/). From version
`1.0.0` onward, entries are generated automatically with `release-it` from
*Conventional Commits* messages.

## [Unreleased]

### Added
- `clientes` entity as the root of the relational model, with foreign keys from the four tramite types.
- Real authentication with a users table, `bcrypt` hashing, roles (`admin` / `operador`), and a JWT in an `httpOnly` cookie.
- Audit log (`logs_auditoria`) that records every decryption of a client's credentials.
- Brute-force protection and *rate limiting* backed by Redis.
- Prometheus-compatible `/metrics` endpoint and a provisioned Grafana dashboard.
- Architecture Decision Records under `docs/decisions/`.

### Changed
- The ETL is now idempotent (upsert by natural key + row hash) and transactional.
- The four CRUD routers are generated from a common factory; encryption lives in a reusable mixin.
- Record deletion is now a soft delete, with a documented retention policy.

### Fixed
- Decryption failures are no longer silenced as "no password".
- `CORS` no longer allows `*` together with `allow_credentials`.
