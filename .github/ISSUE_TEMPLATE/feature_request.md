---
name: Propuesta de funcionalidad
about: Sugiere una mejora o una capacidad nueva
title: "feat: "
labels: ["enhancement"]
assignees: ""
---

## Problema que resuelve

Describe la necesidad operativa concreta. Ejemplo: "la operadora no puede saber
que citas vencen esta semana sin revisar registro por registro".

## Solucion propuesta

Que deberia hacer el sistema.

## Modulo afectado

- [ ] ETL (`etl/`)
- [ ] API / Backend (`backend/`)
- [ ] Dashboard / Frontend (`frontend/`)
- [ ] Infraestructura (Docker, CI/CD, observabilidad)

## Impacto en datos sensibles

- [ ] La funcionalidad **no** accede a credenciales de clientes.
- [ ] La funcionalidad accede a credenciales y por lo tanto requiere registro en `logs_auditoria`.
- [ ] La funcionalidad requiere cambios en el esquema (implica migracion de Alembic y ADR).

## Alternativas consideradas

Que otros enfoques evaluaste y por que los descartaste.
