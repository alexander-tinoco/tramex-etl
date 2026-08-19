import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/**
 * Names in the pictogram repertoire.
 *
 * The set is closed on purpose: a new pictogram is drawn here, on the same
 * grid and with the same weight as the others, instead of being imported
 * from a different library.
 */
export type NombrePictograma =
  | 'sala'
  | 'visa'
  | 'globo'
  | 'pasaporte'
  | 'hoja'
  | 'bitacora'
  | 'buscar'
  | 'llave'
  | 'editar'
  | 'archivar'
  | 'restaurar'
  | 'cerrar'
  | 'anterior'
  | 'siguiente'
  | 'base'
  | 'salir'
  | 'anadir'
  | 'ver'
  | 'ocultar'
  | 'copiar'
  | 'confirmado'
  | 'alerta'
  | 'aviso'
  | 'reloj'
  | 'actualizar'
  | 'volver'
  | 'candado'
  | 'sobre'
  | 'escudo'
  | 'persona';

/**
 * Solid paths, drawn on a 24-unit grid.
 *
 * All of them share the grammar of transit signage: filled silhouette, no
 * outline, geometry legible at small size and from a distance. That's the
 * reason to draw them instead of importing a thin-stroke icon library: a
 * 1.5px line icon belongs to the world of a generic admin panel, not to a
 * control-room sign.
 *
 * A pictogram is one path or several.
 *
 * Most resolve with a single path and `evenodd`, which punches out the inner
 * holes. When one shape overlaps another and must *add* to it instead of
 * punching through it — the diagonal bar of the crossed-out eye, the tip of
 * the restore arrow — separate paths are declared: each fills on its own and
 * the union is additive.
 */
const TRAZADOS: Record<NombrePictograma, string | readonly string[]> = {
  // Access arch: the gate you pass through into control.
  sala: 'M2 21v-8.5C2 7.25 6.48 3 12 3s10 4.25 10 9.5V21h-4.6v-8.5c0-2.9-2.42-5.2-5.4-5.2s-5.4 2.3-5.4 5.2V21H2z',
  // Stamp on a document: the tramite marked at the window.
  visa: 'M4 2h11l5 5v6.4h-3.2V8.4H13V5.2H7.2v13.6h4.1V22H4V2zm12.6 7.9 1.85 3.9 4.15.62-3 3 .71 4.28-3.71-2.02-3.71 2.02.71-4.28-3-3 4.15-.62 1.85-3.9z',
  // Globe with meridians: the tramite that crosses borders.
  globo: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.6 2.3v3.05H6.9A8.1 8.1 0 0 1 10.4 4.3zM13.6 4.3a8.1 8.1 0 0 1 3.5 3.05h-3.5V4.3zM5.55 9.35h4.85v2.05H4.15a7.9 7.9 0 0 1 1.4-2.05zm8.05 0h4.85a7.9 7.9 0 0 1 1.4 2.05h-6.25V9.35zM4.15 13.4h6.25v2.05H5.55a7.9 7.9 0 0 1-1.4-2.05zm9.45 0h6.25a7.9 7.9 0 0 1-1.4 2.05H13.6V13.4zM6.9 17.45h3.5v3.05a8.1 8.1 0 0 1-3.5-3.05zm6.7 0h3.5a8.1 8.1 0 0 1-3.5 3.05v-3.05z',
  // Passport booklet with its emblem.
  pasaporte: 'M5 2h13a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm6.5 3.4a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2zM7.6 16.1h7.8v1.9H7.6v-1.9z',
  // Maple leaf: the Canadian tramite.
  hoja: 'M12 2.2l1.55 2.9c.18.32.5.29.82.11l1.12-.58-.83 4.42c-.18.82.4.82.67.5l1.96-2.2.53 1.25c.13.3.36.26.63.2l2-.42-.72 2.63c-.15.58-.28.82.16 1.03l.85.4-4.1 3.32c-.4.32-.28.42-.14.9l.36 1.18-3.87-.73c-.24-.04-.5.02-.5.32l.18 4.1h-1.4l.17-4.1c0-.3-.25-.36-.5-.32l-3.86.73.36-1.18c.14-.48.26-.58-.14-.9L3.3 12.4l.85-.4c.44-.2.3-.45.16-1.03L3.6 8.34l2 .42c.27.06.5.1.63-.2l.53-1.25 1.96 2.2c.28.32.85.32.67-.5L8.56 4.6l1.12.58c.32.18.64.2.82-.11L12 2.2z',
  // Foliated logbook: the log kept at the window.
  bitacora: 'M4 2h12l4 4v16H4V2zm3 6v2h10V8H7zm0 4.5v2h10v-2H7zm0 4.5v2h6.5v-2H7z',
  buscar: 'M10.4 2a8.4 8.4 0 1 0 5.02 15.14l4.72 4.72 2.12-2.12-4.72-4.72A8.4 8.4 0 0 0 10.4 2zm0 3.2a5.2 5.2 0 1 1 0 10.4 5.2 5.2 0 0 1 0-10.4z',
  // Key: the credential in custody. Only ever rendered in gold.
  llave: 'M15.6 2a6.4 6.4 0 0 0-6.13 8.27L2 17.74V22h4.26v-2.4h2.4v-2.4h2.4l2.67-2.67A6.4 6.4 0 1 0 15.6 2zm1.6 3.2a2 2 0 1 1 0 4 2 2 0 0 1 0-4z',
  editar: 'M17.8 2 22 6.2l-2.5 2.5-4.2-4.2L17.8 2zM13.6 6.2l4.2 4.2L7.4 20.8 2 22l1.2-5.4L13.6 6.2z',
  archivar: 'M2 3h20v5H2V3zm1.6 6.6h16.8V21H3.6V9.6zM8.4 12.6v2.2h7.2v-2.2H8.4z',
  restaurar: [
    'M12 3.6A8.4 8.4 0 1 1 3.6 12h3A5.4 5.4 0 1 0 12 6.6V3.6z',
    'M13.4 0 13.4 7.2 6.6 3.6 13.4 0z',
  ],
  cerrar: 'M5.1 2.9 12 9.8l6.9-6.9 2.2 2.2-6.9 6.9 6.9 6.9-2.2 2.2-6.9-6.9-6.9 6.9-2.2-2.2 6.9-6.9-6.9-6.9 2.2-2.2z',
  anterior: 'M15.6 2.9 6.5 12l9.1 9.1 2.2-2.2L11 12l6.8-6.9-2.2-2.2z',
  siguiente: 'M8.4 2.9 6.2 5.1 13 12l-6.8 6.9 2.2 2.2L17.5 12 8.4 2.9z',
  base: 'M12 2c-4.7 0-8.4 1.34-8.4 3v2.4c0 1.66 3.7 3 8.4 3s8.4-1.34 8.4-3V5c0-1.66-3.7-3-8.4-3zM3.6 9.6V13c0 1.66 3.7 3 8.4 3s8.4-1.34 8.4-3V9.6c-1.9 1.3-5.1 1.9-8.4 1.9s-6.5-.6-8.4-1.9zm0 5.9V19c0 1.66 3.7 3 8.4 3s8.4-1.34 8.4-3v-3.5c-1.9 1.3-5.1 1.9-8.4 1.9s-6.5-.6-8.4-1.9z',
  salir: 'M10.4 2v10.4h3.2V2h-3.2zM6.6 4.6A9.6 9.6 0 1 0 17.4 4.6l-1.8 2.65a6.4 6.4 0 1 1-7.2 0L6.6 4.6z',
  anadir: 'M10.4 3.2h3.2v7.2h7.2v3.2h-7.2v7.2h-3.2v-7.2H3.2v-3.2h7.2V3.2z',
  ver: 'M12 4.5C6.9 4.5 2.6 7.6 1 12c1.6 4.4 5.9 7.5 11 7.5s9.4-3.1 11-7.5c-1.6-4.4-5.9-7.5-11-7.5zm0 3.2a4.3 4.3 0 1 1 0 8.6 4.3 4.3 0 0 1 0-8.6zm0 2.4a1.9 1.9 0 1 0 0 3.8 1.9 1.9 0 0 0 0-3.8z',
  ocultar: [
    'M12 4.5C6.9 4.5 2.6 7.6 1 12c1.6 4.4 5.9 7.5 11 7.5s9.4-3.1 11-7.5c-1.6-4.4-5.9-7.5-11-7.5zm0 3.2a4.3 4.3 0 1 1 0 8.6 4.3 4.3 0 0 1 0-8.6zm0 2.4a1.9 1.9 0 1 0 0 3.8 1.9 1.9 0 0 0 0-3.8z',
    'M3.55 1.2 22.8 20.45l-2.35 2.35L1.2 3.55 3.55 1.2z',
  ],
  copiar: 'M8 2h11a1 1 0 0 1 1 1v13h-3.2V5.2H8V2zM5 6.8h9.8a1 1 0 0 1 1 1V21a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7.8a1 1 0 0 1 1-1z',
  confirmado: 'M9.4 19.2 1.8 11.6l2.55-2.55 5.05 5.05L19.65 3.85 22.2 6.4 9.4 19.2z',
  alerta: 'M12 2 23 21H1L12 2zm-1.4 6.8v6h2.8v-6h-2.8zm0 7.6v2.4h2.8v-2.4h-2.8z',
  aviso: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.4 4.4h2.8v7.2h-2.8V6.4zm0 9.2h2.8v2.8h-2.8v-2.8z',
  reloj: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm-1.4 4.4v6.4l5.1 3.05 1.2-2-4.1-2.45V6.4h-2.2z',
  actualizar: 'M12 3a9 9 0 0 1 7.8 4.5V4.2h2.8v8.4h-8.4V9.8h3.9A6.2 6.2 0 1 0 18 14.5l2.75.9A9 9 0 1 1 12 3z',
  volver: 'M11 3.6 2.6 12 11 20.4l2.2-2.2L8.6 13.6H22v-3.2H8.6l4.6-4.6L11 3.6z',
  candado: 'M12 2a5 5 0 0 0-5 5v2.4H5.4V22h13.2V9.4H17V7a5 5 0 0 0-5-5zm0 3a2 2 0 0 1 2 2v2.4h-4V7a2 2 0 0 1 2-2zm0 9a1.8 1.8 0 0 1 .9 3.36V19h-1.8v-1.64A1.8 1.8 0 0 1 12 14z',
  sobre: 'M2 4.6h20v14.8H2V4.6zm2.9 2.2L12 12.3l7.1-5.5H4.9z',
  escudo: 'M12 2 3.2 5.6v6c0 5 3.75 9.7 8.8 10.4 5.05-.7 8.8-5.4 8.8-10.4v-6L12 2zm-1.35 13.8-3.5-3.5 1.9-1.9 1.6 1.6 4.3-4.3 1.9 1.9-6.2 6.2z',
  persona: 'M12 2.4a4.4 4.4 0 1 1 0 8.8 4.4 4.4 0 0 1 0-8.8zM3.6 21.6c0-4.64 3.76-8.4 8.4-8.4s8.4 3.76 8.4 8.4H3.6z',
};

/**
 * System pictogram.
 *
 * Decorative by default (`aria-hidden`): the label next to the pictogram is
 * what screen readers pick up. When a pictogram travels alone, whoever uses
 * it passes `etiqueta`, and it announces itself as an image with an
 * accessible name instead.
 */
@Component({
  selector: 'app-picto',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      class="picto"
      [attr.width]="tamano()"
      [attr.height]="tamano()"
      viewBox="0 0 24 24"
      [attr.role]="etiqueta() ? 'img' : null"
      [attr.aria-label]="etiqueta() || null"
      [attr.aria-hidden]="etiqueta() ? null : 'true'"
      [attr.focusable]="false"
    >
      @for (d of trazados(); track d) {
        <path [attr.d]="d" fill="currentColor" fill-rule="evenodd" />
      }
    </svg>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
        line-height: 0;
      }
      .picto {
        display: block;
      }
    `,
  ],
})
export class PictogramaComponent {
  readonly nombre = input.required<NombrePictograma>();
  readonly tamano = input<number>(20);
  readonly etiqueta = input<string>('');

  /** Normalizes to a list: a single-path pictogram is iterated the same way. */
  readonly trazados = computed(() => {
    const valor = TRAZADOS[this.nombre()];
    return typeof valor === 'string' ? [valor] : valor;
  });
}
