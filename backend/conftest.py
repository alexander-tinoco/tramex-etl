"""
Test environment configuration.

pytest imports this file before any application module, which makes it the
place to set the variables `app.config` validates on import. This way
`pytest` runs without preparing the environment by hand and without pulling
in whoever runs the suite's development `.env` values.
"""

import os

VALORES_DE_PRUEBA = {
    # Valid Fernet key generated exclusively for the suite. It doesn't
    # encrypt any real data and must not be used outside the tests.
    "TRAMEX_FERNET_KEY": "CxNCUQhBIDIRsETw8i-dfZBdmcnh6YX43VWS-9txMY4=",
    "DATABASE_URL": "sqlite:///:memory:",
    "API_SECRET_KEY": "clave-de-pruebas-sin-valor-en-produccion",
    "APP_ENV": "development",
    "ALLOWED_ORIGINS": "http://testserver",
    "LOG_LEVEL": "WARNING",
    "SENTRY_DSN": "",
    # Minimum bcrypt cost: the suite signs in dozens of times, and at
    # production cost it would take longer to derive hashes than to test anything.
    "BCRYPT_RONDAS": "4",
}

for clave, valor in VALORES_DE_PRUEBA.items():
    os.environ[clave] = valor
