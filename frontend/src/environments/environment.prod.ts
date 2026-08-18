/**
 * Entorno de produccion.
 *
 * Nginx sirve el dashboard y hace de proxy inverso hacia la API bajo el mismo
 * origen, asi que la ruta es relativa: no hay dominio que configurar por
 * despliegue ni CORS que negociar.
 */
export const environment = {
  production: true,
  apiUrl: '/api/v1',
  healthUrl: '/health',
};
