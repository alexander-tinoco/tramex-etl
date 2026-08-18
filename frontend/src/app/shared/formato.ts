/**
 * Utilidades de presentacion compartidas.
 *
 * Viven aqui, y no duplicadas en cada componente, porque la forma de mostrar
 * un valor ausente o una fecha debe ser la misma en toda la interfaz.
 */

/** Marcador visual de un campo sin valor. */
export const SIN_VALOR = '—';

export function formatearTexto(valor: unknown): string {
  if (valor === null || valor === undefined || valor === '') {
    return SIN_VALOR;
  }
  return String(valor);
}

export function formatearFecha(valor: unknown): string {
  if (!valor) {
    return SIN_VALOR;
  }
  const fecha = new Date(String(valor));
  if (Number.isNaN(fecha.getTime())) {
    // El backend puede devolver texto libre en campos de fecha (el archivo de
    // origen contiene celdas como "MARZO"); se muestra tal cual en vez de
    // "Invalid Date".
    return String(valor);
  }
  return fecha.toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: '2-digit' });
}

export function formatearFechaHora(valor: unknown): string {
  if (!valor) {
    return SIN_VALOR;
  }
  const fecha = new Date(String(valor));
  if (Number.isNaN(fecha.getTime())) {
    return String(valor);
  }
  return fecha.toLocaleString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatearValor(valor: unknown, formato?: 'texto' | 'fecha' | 'fechaHora'): string {
  switch (formato) {
    case 'fecha':
      return formatearFecha(valor);
    case 'fechaHora':
      return formatearFechaHora(valor);
    default:
      return formatearTexto(valor);
  }
}
