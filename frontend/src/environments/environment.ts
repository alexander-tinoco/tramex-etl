/**
 * Entorno de desarrollo.
 *
 * La URL de la API es relativa igual que en produccion. El servidor de Angular
 * reenvia `/api` al backend mediante `proxy.conf.json`, de modo que el
 * navegador ve un unico origen: sin eso, la cookie de sesion `httpOnly` no
 * viajaria entre localhost:4200 y localhost:8000 y el login no funcionaria en
 * local aunque si en produccion.
 */
export const environment = {
  production: false,
  apiUrl: '/api/v1',
  healthUrl: '/health',
};
