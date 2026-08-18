# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
versionado se adhiere a [Versionado Semantico](https://semver.org/lang/es/).
A partir de la version `1.0.0` las entradas se generan automaticamente con
`release-it` a partir de los mensajes de *Conventional Commits*.

## [Unreleased]

### Added
- Entidad `clientes` como raiz del modelo relacional, con claves foraneas desde los cuatro tipos de tramite.
- Autenticacion real con tabla de usuarios, hash `bcrypt`, roles (`admin` / `operador`) y JWT en cookie `httpOnly`.
- Bitacora de auditoria (`logs_auditoria`) que registra cada descifrado de credenciales de cliente.
- Proteccion contra fuerza bruta y *rate limiting* respaldados por Redis.
- Endpoint `/metrics` compatible con Prometheus y panel de Grafana aprovisionado.
- Architecture Decision Records en `docs/decisions/`.

### Changed
- El ETL es ahora idempotente (upsert por clave natural + hash de fila) y transaccional.
- Los cuatro routers CRUD se generan desde una fabrica comun; el cifrado vive en un mixin reutilizable.
- El borrado de registros es logico (`soft delete`) con politica de retencion documentada.

### Fixed
- Los fallos de descifrado ya no se silencian como "sin contrasena".
- `CORS` deja de permitir `*` junto con `allow_credentials`.
