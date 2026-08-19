/**
 * Shared presentation utilities.
 *
 * They live here, instead of being duplicated in every component, because
 * how a missing value or a date is displayed must be the same across the
 * whole interface.
 */

/** Visual placeholder for a field with no value. */
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
    // The backend can return free text in date fields (the source file
    // contains cells like "MARCH"); it's shown as-is instead of
    // "Invalid Date".
    return String(valor);
  }
  return fecha.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' });
}

export function formatearFechaHora(valor: unknown): string {
  if (!valor) {
    return SIN_VALOR;
  }
  const fecha = new Date(String(valor));
  if (Number.isNaN(fecha.getTime())) {
    return String(valor);
  }
  return fecha.toLocaleString('en-US', {
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
