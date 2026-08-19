# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
versioning adheres to [Semantic Versioning](https://semver.org/). From version
`1.0.0` onward, entries are generated automatically with `release-it` from
*Conventional Commits* messages.

## [Unreleased]

## [2.0.4] - 2026-08-19

### Fixed
- The vulnerability scan still failed after authenticating: `docker/metadata-action`'s `semver` tag strips the leading `v` when publishing (`v2.0.3` → `2.0.3`), but the scan job pulled by `github.ref_name`, which keeps it — a tag that was never published. The scan now resolves the same tag the publish job actually pushed.

## [2.0.3] - 2026-08-19

### Fixed
- The vulnerability-scan job never authenticated to GHCR before asking Trivy to pull the image, and GHCR packages default to private on first publish regardless of the repository's own visibility. Added a `docker/login-action` step ahead of the scan.

## [2.0.2] - 2026-08-19

### Fixed
- `trivy-action@v0.28.0` still failed after the previous fix: that tag references `aquasecurity/setup-trivy@v0.2.1` internally, which no longer exists upstream. Upgraded to `v0.36.0`, which pins its internal dependency by commit hash instead of by tag.

## [2.0.1] - 2026-08-19

### Fixed
- The CD workflow's vulnerability-scan step referenced `aquasecurity/trivy-action@0.28.0`, a tag that doesn't exist (the action's tags are `v`-prefixed), which made both scan jobs fail outright. Pinned to `v0.28.0`.

## [2.0.0] - 2026-08-18

### Added
- `clientes` entity as the root of the relational model, with foreign keys from the four tramite types and a two-pass fuzzy identity-resolution algorithm.
- Real authentication with a users table, `bcrypt` hashing, roles (`admin` / `operador`), and a JWT in an `httpOnly` cookie.
- Audit log (`logs_auditoria`) that records every decryption of a client's credentials, with severity levels and a filterable admin panel.
- Brute-force protection and *rate limiting* backed by Redis.
- Prometheus-compatible `/metrics` endpoint and a provisioned Grafana dashboard covering traffic, latency and credential-access security metrics.
- Architecture Decision Records under `docs/decisions/`, and a synthetic demo-data generator for local development.
- Optional ordering of tramite listings by recency (`orden=reciente`), used by the dashboard's activity board.
- Issue and pull request templates, Dependabot policy, and a split CI/CD pipeline with a schema-drift check and secret scanning.

### Changed
- The ETL is now idempotent (upsert by natural key + row hash) and transactional.
- The four CRUD routers are generated from a common factory; encryption lives in a reusable mixin.
- Record deletion is now a soft delete, with a documented retention policy.
- The Angular frontend was rewritten with a typed API layer, signals, standalone components and functional guards/interceptors, replacing a single monolithic component.
- The frontend was redesigned end to end around the real Tramex brand: a border-control-signage visual system with a palette measured from the logo, custom solid pictograms, and accessible typography for transcribable data.
- Docker images were hardened and split into development and production stacks.
- Every comment, docstring, log message and UI string across the backend, ETL, shared package and frontend was translated from Spanish to English, along with the README, ADRs and CI configuration.

### Fixed
- Decryption failures are no longer silenced as "no password".
- `CORS` no longer allows `*` together with `allow_credentials`.
- A modal-rendering bug, an admin-guard race condition on direct navigation, and a Docker dev-proxy issue.
- Gitleaks false positives on fixed test credentials.
- A mismatch between the ETL's translated idempotency message and the CI check asserting against it.
