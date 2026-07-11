-- Esquema destino del ETL de TRAMEX.xlsx
-- Solo se guardan los campos que definiste. Las contraseñas viajan
-- cifradas (Fernet/AES) desde el ETL, nunca en texto plano.
-- Ejecutar una sola vez contra tu base PostgreSQL:
--   psql "$DATABASE_URL" -f schema.sql

CREATE TABLE IF NOT EXISTS master_tramex (
    id                  SERIAL PRIMARY KEY,
    nombre              TEXT NOT NULL,
    id_solicitud        TEXT,
    telefono            TEXT,
    numero_pasaporte    TEXT,
    tramite             TEXT,
    cita                TEXT,
    correo_electronico  TEXT,
    contrasena_cifrada  TEXT,
    cargado_en          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS global_entry (
    id                  SERIAL PRIMARY KEY,
    nombre              TEXT NOT NULL,
    apellido            TEXT,
    correo_electronico  TEXT,
    numero_pasaporte    TEXT,
    contrasena_cifrada  TEXT,       -- antes "Número de la cuenta", en la práctica es la contraseña de acceso
    cargado_en          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pasaportes (
    id                  SERIAL PRIMARY KEY,
    nombre              TEXT NOT NULL,
    apellido            TEXT,
    telefono            TEXT,
    lugar_cita          TEXT,
    fecha_cita          DATE,       -- NULL cuando la celda original no era una fecha válida
    fecha_cita_original TEXT,       -- valor crudo (ej. "MARZO") cuando no se pudo convertir
    cargado_en          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS canada (
    id                  SERIAL PRIMARY KEY,
    nombre              TEXT NOT NULL,
    cuenta_ircc         TEXT,
    telefono            TEXT,
    numero_pasaporte    TEXT,
    contrasena_cifrada  TEXT,       -- antes "Cuenta Cita"
    cargado_en          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_master_tramex_pasaporte ON master_tramex (numero_pasaporte);
CREATE INDEX IF NOT EXISTS idx_global_entry_pasaporte  ON global_entry (numero_pasaporte);
CREATE INDEX IF NOT EXISTS idx_canada_pasaporte        ON canada (numero_pasaporte);
