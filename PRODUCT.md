# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Operadoras de la agencia Tramex.** Un equipo pequeño que gestiona trámites
migratorios en nombre de sus clientes: visas americanas, Global Entry,
pasaportes y trámites de Canadá (cuenta IRCC).

El trabajo pesado ocurre **en computadoras de escritorio, en la oficina**, con
el sistema abierto durante toda la jornada mientras se atiende a clientes. Pero
existe una segunda escena de uso confirmada y frecuente: **consulta desde el
teléfono fuera de la oficina** — en la fila del consulado, acompañando a un
cliente a una cita, verificando un dato sobre la marcha. En esa situación lo que
se necesita es buscar a una persona y leer sus datos, incluida la credencial de
su cuenta, no capturar registros nuevos.

Existen dos roles reales:

- **`operador`** — atiende trámites: alta, consulta, edición y baja de
  registros, y consulta de las credenciales de las cuentas de los clientes.
- **`admin`** — además administra usuarios, consulta la bitácora de auditoría y
  ejecuta la política de retención.

## Product Purpose

Sustituir la hoja de cálculo compartida sobre la que operaba la agencia.

Aquel archivo concentraba los expedientes de los clientes y, en celdas de texto
plano junto al nombre y al número de pasaporte, **las contraseñas de las cuentas
consulares de esas personas** — porque la agencia necesita entrar a esas cuentas
para gestionar los trámites en su nombre.

El sistema tiene éxito cuando una operadora encuentra a una persona y todo su
expediente en segundos, obtiene la credencial que necesita para entrar al portal
correspondiente, y todo ello queda registrado sin que tenga que hacer nada
adicional para que quede registrado.

## Positioning

El mecanismo que distingue al sistema no es el CRUD, sino **la custodia
auditable de credenciales ajenas**:

- Las credenciales de los clientes se **cifran de forma reversible** (Fernet),
  no se hashean, porque el trabajo consiste en recuperarlas y usarlas. Un hash
  las haría inservibles.
- Como el dato es recuperable, el control es de acceso y no criptográfico: cada
  descifrado queda asentado con usuario, fecha, IP y registro, y el sistema le
  devuelve a quien consulta el número de asiento que acaba de generar.
- La ingesta del archivo operativo es **idempotente**: reconciliar el mismo
  Excel no duplica ni reescribe nada.

## Operating Context

- **Origen de los datos:** un archivo `TRAMEX.xlsx` mantenido a mano durante
  años, con cuatro hojas heterogéneas (`Master Tramex`, `Global entry`,
  `Pasaportes`, `Canada`). La hoja principal arrastra cuatro filas de títulos
  antes del encabezado real; hay filas de relleno y de totales sin nombre;
  algunas capturas de la misma persona están duplicadas con distinto espaciado;
  la columna de fecha mezcla fechas reales con texto libre (`"MARZO"`,
  `"pendiente"`); los teléfonos vienen en formatos heterogéneos.
- **Portales externos:** la operadora alterna entre este sistema y los portales
  consulares (CGI/USVISA, Global Entry, IRCC), copiando credenciales de uno al
  otro. Ese trasvase es el momento de mayor fricción del día.
- **Jornada:** el sistema permanece abierto durante horas; no es una herramienta
  de visitas puntuales.

## Capabilities and Constraints

**Capacidades confirmadas**

- Ingesta del Excel con resolución de identidad: cuatro hojas sin relación entre
  sí se consolidan en personas únicas.
- CRUD de los cuatro tipos de trámite, siempre colgando de un cliente.
- Consulta auditada de credenciales cifradas.
- Baja lógica reversible y política de retención con purga definitiva.
- Autenticación con sesión en cookie `httpOnly`, dos roles y bloqueo por fuerza
  bruta.
- Bitácora de auditoría consultable y filtrable.

**Restricciones**

- **Escala: cientos de clientes** (entre 100 y 1.000 personas), con unos pocos
  trámites nuevos al día. La búsqueda simple por nombre es suficiente; no hacen
  falta filtros combinados ni paginación por cursor. Las decisiones no deben
  impedir crecer, pero tampoco deben pagar por complejidad que hoy nadie usa.
- La escena móvil es de **lectura y búsqueda**, no de captura.

**Terminología del dominio** (usada por el equipo y presente en los datos)

`trámite`, `cita`, `expediente`, `Master Tramex`, `Global Entry`, `IRCC`,
`cuenta`, `pasaporte`. La interfaz usa el vocabulario del equipo, no
traducciones genéricas.

**Explícitamente indeciso**

- Rotación de la llave de cifrado (hoy exige re-cifrar la base a mano).
- Fusión asistida de personas homónimas que quedaron separadas.
- Ejecución programada de la purga por retención.
- No hay entorno desplegado públicamente.

## Brand Commitments

**Tramex es una agencia real y el logotipo proporcionado es el definitivo.** La
identidad debe respetarse tal cual; no deben inventarse reclamos, servicios,
sedes, cifras ni testimonios.

- **Nombre:** Tramex.
- **Logotipo:** `Logo tramex.png` — un globo terráqueo con un pasaporte, una
  llave y un avión, en verde petróleo y salvia, con el nombre en versalitas
  bajo la marca.
- **Paleta extraída del logotipo** (medida sobre el archivo, no estimada):

  | Rol | Hex | Presencia en el logo |
  |---|---|---|
  | Verde petróleo profundo | `#003C48` | 37 % — color dominante: pasaporte, trazo del globo |
  | Verde salvia | `#84C0A8` | 23 % — relleno del globo |
  | Azul acero | `#185868` | wordmark «TRAMEX» |
  | Dorado | `#C8B060` | franja del pasaporte; acento mínimo (42 px) |

- **Voz:** sobria y directa. El sistema maneja datos personales y credenciales
  de terceros; el tono no admite ni jerga corporativa ni informalidad.

## Evidence on Hand

- **Logotipo oficial:** `/home/alexander-tinoco/Descargas/Logo tramex.png`
  (500×500 PNG). Es el único activo de marca existente.
- **Datos sintéticos:** `docs/generar_datos_demo.py` genera un archivo con la
  estructura y las rarezas del real. **No existe ni debe existir en el
  repositorio ningún dato real de clientes**: nombres, teléfonos, correos,
  números de pasaporte ni credenciales.
- **No existe** — y no debe fabricarse — material de marca adicional:
  fotografías del equipo, testimonios de clientes, cifras de trámites
  resueltos, sedes, certificaciones ni acuerdos con ninguna autoridad
  migratoria.

## Product Principles

1. **La credencial es el centro de gravedad.** Todo el sistema existe para que
   una operadora obtenga una contraseña ajena de forma rápida y trazable. Esa
   operación merece el tratamiento visual y de interacción más cuidado, no el de
   un botón más de la fila.
2. **El rastro no se pide, ocurre.** La auditoría nunca puede depender de que
   alguien recuerde activarla, y quien consulta debe ver que quedó registrado.
3. **El dato sucio se preserva, no se descarta.** Una fecha escrita como
   `"MARZO"` es información que la operadora sabe interpretar; el sistema la
   conserva en lugar de perderla al normalizar.
4. **Una persona, un expediente.** El valor sobre la hoja de cálculo es que los
   cuatro trámites de alguien dejen de ser cuatro filas sin relación.
5. **Nada se destruye por accidente.** Con datos personales, toda baja es
   reversible y auditada; la destrucción es una operación aparte, explícita.

## Accessibility & Inclusion

- **Interfaz en español**, con el vocabulario del equipo.
- **Uso prolongado:** el sistema permanece abierto toda la jornada, lo que
  vuelve prioritarios el contraste sostenido y la legibilidad a distancia de
  lectura, por encima del impacto de la primera impresión.
- **Escena móvil real:** buscar y leer debe funcionar en un teléfono, de pie y
  con una sola mano.
- **Datos de alta precisión:** números de pasaporte, teléfonos y credenciales se
  transcriben a mano a otros portales. Distinguir `l` de `I` y `0` de `O` no es
  un detalle tipográfico, es prevención de errores.
