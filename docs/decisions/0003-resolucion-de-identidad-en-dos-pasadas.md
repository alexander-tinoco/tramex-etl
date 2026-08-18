# 0003 · Resolución de identidad de personas en dos pasadas

## Estado

Aceptado · 2026-07-11

## Contexto

El archivo de origen tiene cuatro hojas y **ninguna relación entre ellas**. La
misma persona aparece en varias, escrita de forma distinta cada vez:

| Hoja | Nombre | Apellido | Pasaporte | Correo |
|---|---|---|---|---|
| Master Tramex | `José Ramírez` | — | `G111` | `jose@…` |
| Canadá | `José Ramírez` | — | `G111` | — |
| Global entry | `Ana` | `Lopez` | `G222` | `ana@…` |
| Pasaportes | `Ana` | `Lopez` | — | — |

Tres problemas simultáneos:

1. Unas hojas guardan el nombre completo en una columna y otras lo parten en dos.
2. No todas las hojas capturan los mismos identificadores: **la hoja de
   Pasaportes no tiene ni pasaporte ni correo**.
3. La misma persona se escribe con acentos, espacios y capitalización variables.

Al introducir la entidad `clientes` había que decidir cómo se deduce que cuatro
filas de cuatro hojas son la misma persona. La primera implementación usó
directamente los campos disponibles, y en pruebas contra datos heredados
**fragmentó a José Ramírez en dos clientes** solo porque la hoja de Canadá no
traía correo.

## Decisión

La identidad de una persona se compone de dos partes:

```
clave_cliente = SHA256( nombre_canónico ‖ identificador_fuerte )
```

- **`nombre_canónico`**: nombre y apellido unidos, sin acentos, con espacios
  colapsados y en minúsculas. Hace comparables `"José Ramírez"` y `"Ana"/"Lopez"`
  vengan de la hoja que vengan.
- **`identificador_fuerte`**: el número de pasaporte si existe; si no, el correo;
  si no hay ninguno, cadena vacía (clave *débil*).

Sobre esa base, la resolución recorre los datos **en dos pasadas**:

**Primera pasada — filas con identificador fuerte.** Son las que definen quién es
quién. Cada clave nueva da de alta una persona.

**Segunda pasada — filas sin identificador fuerte.** Se busca por nombre canónico
entre las personas ya conocidas:

- Si hay **exactamente una** coincidencia, la fila se enlaza a ella. Es el caso
  de la hoja de Pasaportes, que si no quedaría desconectada del resto del
  expediente de esa persona.
- Si hay **varias** (homónimos), se crea una persona nueva.

### Por qué ante la ambigüedad se separa y no se une

Es asimétrico a propósito. Si dos expedientes quedan sueltos y eran de la misma
persona, unirlos después es trivial. Si dos expedientes se fusionan por error, se
ha mezclado el pasaporte de una persona con la cita de otra, y **separarlos exige
saber qué fila era de quién**, información que ya se perdió. Además, en este
dominio una fusión equivocada significa mostrar a una operadora las credenciales
de una persona distinta.

Por eso, ante la duda, el sistema prefiere el error recuperable.

## Consecuencias

- **Las personas sin ningún identificador duro pueden fragmentarse.** Dos «Ana
  Lopez» sin pasaporte serán dos clientes. Es el comportamiento deseado, pero
  implica que el conteo de clientes es una cota superior de las personas reales.
- **Añadir el pasaporte a una ficha cambia su clave natural.** Se resuelve
  recalculándola; está pendiente automatizar la fusión asistida desde la
  interfaz.
- **La segunda pasada carga los clientes activos en memoria.** Aceptable para el
  volumen de una agencia (cientos de personas); a escala mayor habría que
  indexar el nombre canónico como columna generada.
- **El ETL, la API y la migración comparten el algoritmo.** Está verificado con
  pruebas en los tres puntos de entrada.

## Verificación

La migración se probó sobre datos heredados con las cuatro hojas: **seis filas
de trámite se resolvieron en dos clientes**, incluida la fila de Pasaportes sin
identificador fuerte, que quedó correctamente enlazada. Una prueba dedicada
comprueba que dos homónimos sin identificador **no** se fusionan.
