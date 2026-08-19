---
name: Feature request
about: Suggest an improvement or a new capability
title: "feat: "
labels: ["enhancement"]
assignees: ""
---

## Problem it solves

Describe the concrete operational need. Example: "the operator has no way to
tell which appointments expire this week without checking record by record".

## Proposed solution

What should the system do.

## Affected module

- [ ] ETL (`etl/`)
- [ ] API / Backend (`backend/`)
- [ ] Dashboard / Frontend (`frontend/`)
- [ ] Infrastructure (Docker, CI/CD, observability)

## Impact on sensitive data

- [ ] The feature does **not** access client credentials.
- [ ] The feature accesses credentials and therefore requires logging in `logs_auditoria`.
- [ ] The feature requires schema changes (implies an Alembic migration and an ADR).

## Alternatives considered

What other approaches you evaluated and why you ruled them out.
