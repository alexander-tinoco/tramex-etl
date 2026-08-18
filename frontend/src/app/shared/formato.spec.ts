import { SIN_VALOR, formatearFecha, formatearTexto, formatearValor } from './formato';

describe('formato', () => {
  it('muestra un marcador para los valores ausentes', () => {
    expect(formatearTexto(null)).toBe(SIN_VALOR);
    expect(formatearTexto(undefined)).toBe(SIN_VALOR);
    expect(formatearTexto('')).toBe(SIN_VALOR);
  });

  it('conserva los valores presentes', () => {
    expect(formatearTexto('Ana Lopez')).toBe('Ana Lopez');
    expect(formatearTexto(0)).toBe('0');
  });

  it('formatea fechas válidas', () => {
    expect(formatearFecha('2026-08-15')).toContain('2026');
  });

  it('muestra tal cual el texto libre en un campo de fecha', () => {
    // El archivo de origen trae celdas como "MARZO"; mostrar "Invalid Date"
    // perderia informacion que la operadora si sabe interpretar.
    expect(formatearFecha('MARZO')).toBe('MARZO');
    expect(formatearFecha('pendiente')).toBe('pendiente');
  });

  it('elige el formato indicado por la columna', () => {
    expect(formatearValor(null, 'fecha')).toBe(SIN_VALOR);
    expect(formatearValor('Ana', 'texto')).toBe('Ana');
  });
});
