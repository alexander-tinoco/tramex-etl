# 0002 · Identidad reproducible de filas y carga idempotente

## Estado

Aceptado · 2026-07-11

## Contexto

La primera versión del pipeline cargaba así:

```python
df.to_sql(table_name, engine, if_exists="append", index=False)
```

Con dos consecuencias graves:

1. **Reprocesar el mismo Excel duplicaba toda la base.** El `drop_duplicates()`
   previo solo deduplicaba dentro del DataFrame, nunca contra lo ya cargado. Y
   reprocesar es lo normal: la hoja se edita a diario y hay que volver a cargarla.
2. **No había forma de saber qué había cambiado.** Cada corrida era un volcado
   ciego.

Las filas del archivo no tienen identificador propio: nadie asignó nunca un ID a
un trámite. Lo único disponible es el contenido de la propia fila.

## Decisión

Cada fila lleva dos huellas SHA-256 calculadas a partir de su contenido, con
propósitos distintos:

**`clave_natural`** — huella de los campos que *identifican* la fila (quién es).
Tiene índice único y es el objetivo del `ON CONFLICT` del upsert.

**`hash_fila`** — huella de *todos* los campos de negocio. Permite detectar si
algo cambió realmente.

La carga es entonces:

```sql
INSERT INTO master_tramex (...) VALUES (...)
ON CONFLICT (clave_natural) WHERE eliminado_en IS NULL
DO UPDATE SET ...
WHERE master_tramex.hash_fila IS DISTINCT FROM excluded.hash_fila;
```

Propiedades que se obtienen:

- **Idempotencia.** Reprocesar el mismo archivo no duplica nada.
- **Sin reescrituras inútiles.** Una fila cuyo contenido no cambió no se toca,
  lo que además evita volver a cifrar credenciales intactas.
- **Informe honesto.** El pipeline puede decir cuántas filas son nuevas, cuántas
  cambiaron y cuántas quedaron igual.

### Normalización antes de la huella

Dos capturas de la misma persona deben producir la misma clave. Antes de
digerir, cada valor se normaliza: se quitan acentos (NFKD y descarte de
diacríticos), se colapsan espacios internos, se recortan extremos y se pasa a
minúsculas. Así `"  JOSÉ  Ramírez "` y `"jose ramirez"` convergen.

Los campos se concatenan con un separador de control (`\x1f`) para que la
concatenación sea inyectiva: sin él, `("ab", "c")` y `("a", "bc")` producirían
la misma clave.

### El hash se calcula sobre texto plano, nunca sobre el criptograma

Fernet usa IV aleatorio, así que cifrar dos veces el mismo texto da resultados
distintos. Si `hash_fila` incluyera el criptograma, **toda fila con credencial
parecería modificada en cada corrida** y se reescribiría siempre. Por eso el
hash se calcula antes de cifrar. La contraseña en claro entra al hash pero no se
puede recuperar de él: SHA-256 no es reversible.

### Una sola fuente de verdad

El cálculo vive en el paquete `shared/tramex_shared`, que importan el ETL, la
API y las migraciones. Si cada capa derivara la clave a su manera, un cliente
dado de alta a mano por una operadora y el mismo cliente presente en el Excel
terminarían como dos registros distintos.

## Consecuencias

- **Cambiar `campos_clave` es una migración de datos.** Altera todas las claves
  naturales existentes; hay que recalcularlas.
- **El upsert requiere PostgreSQL o SQLite.** El pipeline rechaza explícitamente
  cualquier otro dialecto en vez de degradar a un `append` silencioso.
- **Hay un coste por lote:** antes de escribir se consulta el estado previo de
  las claves del lote para poder clasificar. Es una consulta indexada más por
  lote, a cambio de un informe fiable.

## Alternativas descartadas

- **`TRUNCATE` y recargar.** Destruiría las altas hechas desde la API y las
  marcas de tiempo de carga original, y dejaría la tabla vacía durante la carga.
- **Comparar fila a fila en Python.** Requiere traer la tabla entera a memoria y
  no aprovecha el índice.
- **Confiar en una clave del archivo** (`ID`, `Cuenta IRCC`). Se comprobó que se
  repiten, se dejan vacías y se reutilizan entre trámites.
