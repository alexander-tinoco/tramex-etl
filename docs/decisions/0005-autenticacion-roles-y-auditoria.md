# 0005 · Autenticación con sesión en cookie, roles y bitácora de auditoría

## Estado

Aceptado · 2026-07-13 · Reemplaza el esquema de credenciales por variables de entorno

## Contexto

La autenticación original era:

```python
if form_data.username != API_USERNAME or form_data.password != API_PASSWORD:
    raise HTTPException(status_code=401, ...)
```

Cuatro problemas en cuatro líneas:

1. **Una sola cuenta compartida.** Imposible saber *quién* hizo qué. En un
   sistema que guarda credenciales de cuentas gubernamentales de terceros, es
   justamente la pregunta que hay que poder responder.
2. **Contraseña en texto plano** en el entorno del proceso.
3. **Comparación con `!=`**, que devuelve en tiempo variable y filtra
   información por temporización.
4. **Sin límite de intentos.** El endpoint era público y se podían probar
   contraseñas indefinidamente.

Además, el token viajaba al navegador y se guardaba en `localStorage`, accesible
desde cualquier script de la página.

## Decisión

### Usuarios con hash bcrypt

Tabla `usuarios` con hash bcrypt (coste 12, configurable; las pruebas lo bajan a
4 porque ahí se ejercita el flujo, no el coste). La contraseña se normaliza con
SHA-256 y base64 antes de bcrypt, porque **bcrypt trunca en 72 bytes en
silencio**: sin ese paso, dos contraseñas largas con el mismo prefijo serían
intercambiables.

Nótese el contraste con [0001](./0001-cifrado-reversible-de-credenciales.md): las
contraseñas *de los usuarios del sistema* se hashean porque solo hay que
verificarlas; las *de las cuentas de los clientes* se cifran porque hay que
devolverlas.

Cuando el correo no existe se verifica igualmente contra un hash señuelo, para
que el tiempo de respuesta no permita enumerar cuentas válidas.

### Sesión en cookie `httpOnly`

El JWT viaja en una cookie `httpOnly`, invisible para JavaScript: un XSS ya no
basta para robar la sesión. Se sigue aceptando `Authorization: Bearer` porque
Swagger, los scripts y las integraciones no usan cookies.

La consecuencia de diseño es que **el frontend no puede leer su propia sesión**,
y por eso pregunta a la API al arrancar (`GET /auth/me`). Es más trabajo que leer
`localStorage`, y es el precio correcto.

Cada petición revalida que el usuario siga existiendo y activo: un JWT sigue
siendo criptográficamente válido después de dar de baja a alguien.

### Dos roles

`operador` gestiona trámites y consulta credenciales de clientes; `admin` además
administra usuarios, lee la bitácora y ejecuta la retención. Solo dos, porque el
equipo real son dos figuras; añadir más sin necesidad produce una matriz de
permisos que nadie mantiene.

El sistema impide degradar o dar de baja al último administrador activo:
recuperarse de eso exigiría editar la base a mano.

### Bitácora de auditoría

`logs_auditoria` registra logins (exitosos, fallidos y bloqueados), altas,
cambios, bajas, restauraciones, purgas y, sobre todo, **cada descifrado de una
credencial de cliente**, con usuario, fecha, IP y registro consultado. La
respuesta del endpoint devuelve el identificador del asiento que acaba de dejar,
y la interfaz lo muestra: quien consulta ve que ha quedado registrado.

La regla es invariable: **se registra qué se consultó, nunca qué se obtuvo.** Un
saneador descarta cualquier campo sensible que llegue por error al detalle y deja
constancia en el log de aplicación para que se corrija el punto de llamada.

### Protección contra fuerza bruta

Bloqueo por cuenta tras N fallos en una ventana (resiste la rotación de IP) más
límite por origen (frena el barrido de muchas cuentas). Los contadores viven en
Redis para que varias réplicas compartan estado; sin Redis hay respaldo en
memoria, y por eso la configuración **exige Redis en producción**.

La ventana no se prorroga con cada intento: si lo hiciera, un atacante constante
mantendría bloqueada indefinidamente una cuenta legítima.

## Consecuencias

- **Arranque en frío.** Crear usuarios exige estar autenticado, así que hay un
  script idempotente que siembra el primer administrador. En desarrollo genera e
  imprime una contraseña; en producción la exige, porque una contraseña impresa
  en los logs del contenedor es una contraseña filtrada.
- **En desarrollo hace falta un proxy.** La cookie no viaja entre
  `localhost:4200` y `localhost:8000`; el servidor de Angular reenvía `/api` para
  que haya un único origen.
- **Las pruebas no simulan la autenticación.** Los clientes de prueba inician
  sesión de verdad contra el endpoint real; sustituirla por un *override* dejaría
  sin cubrir la parte más delicada.

## Fuera de alcance

No hay MFA, ni rotación automática de `API_SECRET_KEY`, ni caducidad de
contraseñas, ni recuperación por correo. Son necesarios si el sistema se expone a
internet abierto; hoy está pensado para la red de la agencia detrás de HTTPS.
