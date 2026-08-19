/**
 * Development environment.
 *
 * The API URL is relative, same as in production. The Angular dev server
 * forwards `/api` to the backend via `proxy.conf.js`, so the browser sees a
 * single origin: without that, the `httpOnly` session cookie wouldn't travel
 * between localhost:4200 and localhost:8000, and login would work in
 * production but not locally.
 */
export const environment = {
  production: false,
  apiUrl: '/api/v1',
  healthUrl: '/health',
};
