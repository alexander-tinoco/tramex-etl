# 0004 · Borrado lógico, unicidad parcial y política de retención

## Estado

Aceptado · 2026-07-12

## Contexto

`DELETE /api/v1/{recurso}/{id}` destruía la fila. En un sistema que custodia
datos personales —nombres, teléfonos, correos, números de pasaporte y
credenciales de cuentas— eso tiene dos problemas: un borrado accidental es
irreversible, y una baja no deja rastro de quién la hizo ni cuándo.

Al mismo tiempo, conservar datos personales indefinidamente tampoco es correcto.

## Decisión

### Borrado lógico

Toda tabla de negocio tiene `eliminado_en`. El `DELETE` de la API marca la fila
en lugar de destruirla; deja de aparecer en los listados pero sigue disponible
con `?incluir_eliminados=true` y puede reactivarse con `POST /{id}/restaurar`.
La baja y la restauración quedan asentadas en la bitácora de auditoría.

### Unicidad parcial

La consecuencia técnica interesante: si `clave_natural` fuera `UNIQUE` a secas,
una fila archivada **seguiría ocupando su clave** e impediría volver a insertar
la versión buena de esa misma identidad. La restricción es por tanto un índice
único **parcial**:

```sql
CREATE UNIQUE INDEX uq_master_tramex_clave_natural_activa
    ON master_tramex (clave_natural) WHERE eliminado_en IS NULL;
```

Así conviven un registro vigente y cualquier número de versiones archivadas de
la misma identidad. El `ON CONFLICT` del ETL apunta a este índice.

Esto resolvió además un problema real que apareció al migrar: la carga
`append`-only anterior había dejado filas duplicadas en la base. La migración las
detecta por clave natural, **conserva la más antigua y archiva las demás** en vez
de destruirlas, y solo entonces impone la unicidad.

### Retención

`POST /api/v1/admin/retencion/ejecutar` destruye definitivamente lo archivado
hace más de `DIAS_RETENCION` días (365 por defecto) y los asientos de auditoría
fuera de ese periodo. Requiere rol `admin`, exige `confirmar=true` explícito y
queda auditado con nivel `ALERTA`.

Es la única operación irreversible del sistema.

### La bitácora no admite borrado lógico

`logs_auditoria` no tiene `eliminado_en` ni endpoint de edición a propósito: una
bitácora que se puede corregir no sirve como bitácora. La única forma legítima de
que desaparezca un asiento es la purga por antigüedad.

## Consecuencias

- **Toda consulta filtra por `eliminado_en IS NULL`.** Está centralizado en
  `CRUDBase`, de modo que un repositorio nuevo lo hereda; olvidarlo expondría
  registros dados de baja.
- **Índices compuestos `(cliente_id, eliminado_en)`** en las cuatro tablas, para
  que el filtro no degrade las consultas por cliente.
- **La base crece más.** Con el volumen de una agencia es irrelevante frente a la
  trazabilidad que aporta.
- **Dar de baja un cliente arrastra sus trámites.** Dejar trámites activos
  colgando de un cliente archivado produciría listados inconsistentes.
- **La purga debe ejecutarse.** Hoy es manual; lo natural es un job programado,
  pendiente.

## Alternativas descartadas

- **Tabla histórica aparte.** Duplica el esquema y obliga a mantener dos
  estructuras sincronizadas.
- **Versionado completo** (tipo *temporal tables*). Responde «cómo era esta fila
  en tal fecha», pregunta que nadie hace en este dominio, a cambio de bastante
  complejidad.
