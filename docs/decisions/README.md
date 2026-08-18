# Architecture Decision Records

Registro de las decisiones técnicas de fondo del proyecto: qué se decidió, en
qué contexto y con qué consecuencias. El objetivo es que quien llegue después
—o yo mismo dentro de un año— no tenga que reconstruir el razonamiento leyendo
el código.

Formato: **Contexto** (qué problema real había) → **Decisión** (qué se hizo) →
**Consecuencias** (qué se ganó y qué se pagó) → **Alternativas descartadas**.

| # | Decisión | Resumen |
|---|---|---|
| [0001](./0001-cifrado-reversible-de-credenciales.md) | Cifrado reversible y no hash para credenciales de clientes | La agencia necesita *recuperar* la contraseña del cliente, no *verificarla*: un hash haría el dato inservible |
| [0002](./0002-identidad-reproducible-y-carga-idempotente.md) | Identidad reproducible de filas y carga idempotente | Dos huellas SHA-256 por fila permiten un upsert que no duplica ni reescribe de más |
| [0003](./0003-resolucion-de-identidad-en-dos-pasadas.md) | Resolución de identidad de personas en dos pasadas | Ante homónimos ambiguos se prefiere separar: unir después es trivial, separar no |
| [0004](./0004-borrado-logico-y-retencion.md) | Borrado lógico, unicidad parcial y retención | Un índice único parcial permite que convivan un registro vigente y sus versiones archivadas |
| [0005](./0005-autenticacion-roles-y-auditoria.md) | Autenticación con cookie, roles y auditoría | Un usuario por persona es lo que hace que «¿quién consultó esa credencial?» tenga respuesta |
| [0006](./0006-paquete-compartido-entre-etl-y-api.md) | Un paquete compartido entre el ETL y la API | Tres componentes escriben en las mismas tablas y deben derivar la identidad igual |
