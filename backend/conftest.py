"""
Configuracion del entorno de pruebas.

pytest importa este archivo antes que cualquier modulo de la aplicacion, asi
que es el lugar donde fijar las variables que `app.config` valida al importarse.
De este modo `pytest` se ejecuta sin preparar el entorno a mano y sin arrastrar
valores del `.env` de desarrollo de quien corre la suite.
"""

import os

VALORES_DE_PRUEBA = {
    # Llave Fernet valida generada exclusivamente para la suite. No cifra
    # ningun dato real y no debe usarse fuera de las pruebas.
    "TRAMEX_FERNET_KEY": "CxNCUQhBIDIRsETw8i-dfZBdmcnh6YX43VWS-9txMY4=",
    "DATABASE_URL": "sqlite:///:memory:",
    "API_SECRET_KEY": "clave-de-pruebas-sin-valor-en-produccion",
    "APP_ENV": "development",
    "ALLOWED_ORIGINS": "http://testserver",
    "LOG_LEVEL": "WARNING",
    "SENTRY_DSN": "",
}

for clave, valor in VALORES_DE_PRUEBA.items():
    os.environ[clave] = valor
