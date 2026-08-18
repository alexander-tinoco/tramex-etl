# 0001 · Cifrado reversible (Fernet) y no hash para las credenciales de clientes

## Estado

Aceptado · 2026-07-10

## Contexto

La agencia gestiona trámites migratorios en nombre de sus clientes. Para hacerlo
necesita **entrar a las cuentas de esos clientes**: el portal consular, la cuenta
de Global Entry, la cuenta IRCC de Canadá. Las contraseñas de esas cuentas
estaban en celdas de un Excel compartido, en texto plano, junto al nombre y al
número de pasaporte de la persona.

La reacción instintiva ante «hay que guardar contraseñas» es *hashearlas con
bcrypt*. Aquí sería un error de categoría.

## Decisión

Las credenciales de clientes se **cifran de forma reversible** con Fernet
(AES-128 en modo CBC con HMAC-SHA256 para autenticación), no se hashean.

El motivo es que hash y cifrado resuelven problemas distintos:

| | Hash (bcrypt) | Cifrado (Fernet) |
|---|---|---|
| Pregunta que responde | «¿es esta la contraseña correcta?» | «¿cuál era la contraseña?» |
| Reversible | No, por diseño | Sí, con la llave |
| Caso de uso | **Verificar** a quien se autentica | **Custodiar** un secreto ajeno |

La agencia no necesita *verificar* la contraseña del cliente: necesita
*recuperarla* para teclearla en el portal correspondiente. Un hash es
irreversible por definición, así que haría el dato inservible.

Por eso conviven los dos mecanismos en el mismo sistema, y es importante no
confundirlos:

- **Contraseñas de los usuarios del sistema** (operadoras y administradores):
  hash bcrypt. El sistema solo necesita verificarlas. Ver [0005](./0005-autenticacion-roles-y-auditoria.md).
- **Credenciales de las cuentas de los clientes**: cifrado Fernet. El sistema
  necesita devolverlas.

### Consecuencias operativas

1. **La llave es el activo crítico.** Quien tenga `TRAMEX_FERNET_KEY` y un
   volcado de la base tiene todas las credenciales. La llave debe vivir en un
   gestor de secretos, nunca junto al respaldo de la base.
2. **Rotar la llave exige re-cifrar.** No basta con cambiar la variable: hay que
   descifrar con la vieja y volver a cifrar con la nueva. Está pendiente
   automatizarlo.
3. **Todo descifrado se audita.** Como el dato es recuperable, el control no
   puede ser criptográfico y tiene que ser de acceso: cada consulta deja asiento
   en `logs_auditoria` con usuario, fecha, IP y registro.
4. **Un fallo al descifrar escala.** Si hay criptograma pero no abre con la llave
   activa, se lanza `ErrorDeDescifrado` y la API responde 500. La versión
   anterior devolvía `None`, indistinguible de «este registro no tiene
   contraseña»: se perdían credenciales de clientes en silencio.

### Por qué Fernet y no AES a mano

Fernet trae por defecto lo que es fácil equivocar implementando AES
directamente: IV aleatorio por mensaje, autenticación con HMAC (protege contra
manipulación del criptograma) y marca temporal. Es una construcción cerrada,
sin parámetros que configurar mal.

Su naturaleza no determinista tiene una consecuencia en el pipeline: cifrar dos
veces el mismo texto produce criptogramas distintos, así que **no se pueden
comparar criptogramas para detectar cambios**. Por eso `hash_fila` se calcula
sobre el texto plano normalizado y nunca sobre el cifrado. Ver
[0002](./0002-identidad-reproducible-y-carga-idempotente.md).

## Alternativas descartadas

- **Hash bcrypt.** Haría el dato irrecuperable e inútil para la operación.
- **Un gestor de contraseñas externo** (Bitwarden, 1Password) con la API
  guardando solo referencias. Es lo correcto a mayor escala y elimina la
  custodia del secreto, pero añade una dependencia externa de pago y un punto de
  fallo para una agencia pequeña. Es la evolución natural si el sistema crece.
- **Cifrado a nivel de columna en PostgreSQL** (`pgcrypto`). Traslada la llave a
  la base de datos, que es justo de donde conviene sacarla: un volcado
  comprometido incluiría entonces todo lo necesario para descifrar.
