"""
Tests for the pipeline's configuration.

They cover failures above all: a pipeline that starts up with the wrong
configuration can write to the wrong database or store credentials the API
won't later be able to decrypt.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from etl.helpers import config
from etl.helpers.config import (
    ErrorDeConfiguracion,
    cargar_dotenv,
    obtener_fernet,
    obtener_url_base_de_datos,
)

LLAVE_VALIDA = "CxNCUQhBIDIRsETw8i-dfZBdmcnh6YX43VWS-9txMY4="


class TestUrlBaseDeDatos:
    def test_devuelve_la_variable_del_entorno(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@host:5432/db")
        assert obtener_url_base_de_datos().endswith("/db")

    def test_sin_variable_falla_en_vez_de_caer_a_sqlite(self, monkeypatch):
        """
        The previous version wrote to a local `tramex.db` if the URL was missing.

        Believing the real database was loaded when a loose local file was
        actually written is an expensive failure that's hard to notice.
        """
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ErrorDeConfiguracion, match="DATABASE_URL"):
            obtener_url_base_de_datos()


class TestFernet:
    def test_construye_el_cifrador_con_una_llave_valida(self, monkeypatch):
        monkeypatch.setenv("TRAMEX_FERNET_KEY", LLAVE_VALIDA)
        cifrador = obtener_fernet()
        assert cifrador.decrypt(cifrador.encrypt(b"secreto")) == b"secreto"

    def test_sin_llave_falla_con_instrucciones(self, monkeypatch):
        monkeypatch.delenv("TRAMEX_FERNET_KEY", raising=False)
        with pytest.raises(ErrorDeConfiguracion, match="generate_key"):
            obtener_fernet()

    def test_una_llave_mal_formada_falla_al_arrancar(self, monkeypatch):
        """
        Better to catch it at startup than halfway through a load of thousands of rows.
        """
        monkeypatch.setenv("TRAMEX_FERNET_KEY", "esto-no-es-una-llave")
        with pytest.raises(ErrorDeConfiguracion, match="base64"):
            obtener_fernet()

    def test_la_llave_generada_por_la_utilidad_es_aceptada(self, monkeypatch):
        monkeypatch.setenv("TRAMEX_FERNET_KEY", Fernet.generate_key().decode())
        assert obtener_fernet() is not None


class TestDotenv:
    def test_carga_las_variables_del_archivo(self, tmp_path, monkeypatch):
        archivo = tmp_path / ".env"
        archivo.write_text(
            "# comentario\n"
            "DATABASE_URL='postgresql+psycopg2://u:p@host:5432/db'\n"
            "\n"
            'TRAMEX_FERNET_KEY="una-llave"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(config, "RUTAS_ENV", (archivo,))
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("TRAMEX_FERNET_KEY", raising=False)

        cargar_dotenv()

        import os

        # Quotes in the file aren't part of the value.
        assert os.environ["DATABASE_URL"] == "postgresql+psycopg2://u:p@host:5432/db"
        assert os.environ["TRAMEX_FERNET_KEY"] == "una-llave"

    def test_el_entorno_real_tiene_prioridad_sobre_el_archivo(self, tmp_path, monkeypatch):
        """
        This is what lets the same command work locally and in a container.

        Locally it reads the `.env`; in deployment it receives injected
        secrets that must not be overwritten by a file left behind in the image.
        """
        archivo = tmp_path / ".env"
        archivo.write_text("DATABASE_URL=del-archivo\n", encoding="utf-8")
        monkeypatch.setattr(config, "RUTAS_ENV", (archivo,))
        monkeypatch.setenv("DATABASE_URL", "del-entorno")

        cargar_dotenv()

        assert obtener_url_base_de_datos() == "del-entorno"

    def test_sin_archivo_no_falla(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "RUTAS_ENV", (tmp_path / "no-existe",))
        cargar_dotenv()
