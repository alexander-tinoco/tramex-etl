import { SIN_VALOR, formatearFecha, formatearTexto, formatearValor } from './formato';

describe('formato', () => {
  it('shows a placeholder for missing values', () => {
    expect(formatearTexto(null)).toBe(SIN_VALOR);
    expect(formatearTexto(undefined)).toBe(SIN_VALOR);
    expect(formatearTexto('')).toBe(SIN_VALOR);
  });

  it('keeps values that are present', () => {
    expect(formatearTexto('Ana Lopez')).toBe('Ana Lopez');
    expect(formatearTexto(0)).toBe('0');
  });

  it('formats valid dates', () => {
    expect(formatearFecha('2026-08-15')).toContain('2026');
  });

  it('shows free-form text in a date field as-is', () => {
    // The source file has cells like "MARZO"; showing "Invalid Date" would
    // lose information the operator can actually interpret.
    expect(formatearFecha('MARZO')).toBe('MARZO');
    expect(formatearFecha('pendiente')).toBe('pendiente');
  });

  it('picks the format indicated by the column', () => {
    expect(formatearValor(null, 'fecha')).toBe(SIN_VALOR);
    expect(formatearValor('Ana', 'texto')).toBe('Ana');
  });
});
