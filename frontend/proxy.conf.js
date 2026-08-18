/**
 * Proxy del servidor de desarrollo de Angular.
 *
 * Reenvia `/api` y `/health` al backend para que el navegador vea un unico
 * origen. Sin esto la cookie de sesion `httpOnly` no viajaria entre
 * localhost:4200 y localhost:8000, y el login funcionaria en produccion pero
 * no en local.
 *
 * El destino es configurable porque cambia segun donde corra el servidor:
 *
 *   - En la maquina de quien desarrolla, la API esta en `localhost:8000`.
 *   - Dentro del contenedor de desarrollo, `localhost` es el propio contenedor
 *     del dashboard; la API responde en el nombre del servicio, `backend`.
 *
 * Por eso este archivo es JavaScript y no JSON: un JSON no puede leer el
 * entorno, y con destino fijo el login falla dentro de Docker con un error
 * genérico difícil de diagnosticar.
 */

const destino = process.env.API_PROXY_TARGET || 'http://localhost:8000';

module.exports = {
  '/api': {
    target: destino,
    secure: false,
    changeOrigin: false,
    logLevel: 'warn',
  },
  '/health': {
    target: destino,
    secure: false,
    changeOrigin: false,
    logLevel: 'warn',
  },
};
