/**
 * Production environment.
 *
 * Nginx serves the dashboard and acts as a reverse proxy to the API under the
 * same origin, so the path is relative: there's no domain to configure per
 * deployment and no CORS to negotiate.
 */
export const environment = {
  production: true,
  apiUrl: '/api/v1',
  healthUrl: '/health',
};
