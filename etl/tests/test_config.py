"""
Pruebas de la configuracion del pipeline.

Cubren sobre todo los fallos: un pipeline que arranca con la configuracion
equivocada puede escribir en la base que no era o guardar credenciales que
despues la API no sabra descifrar.
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
        La version anterior escribia en un `tramex.db` local si faltaba la URL.

        Creer que se cargo la base real cuando en realidad se escribio un
        archivo suelto es un fallo caro y dificil de notar.
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
        Mejor detectarlo al inicio que a mitad de una carga de miles de filas.
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

        # Las comillas del archivo no forman parte del valor.
        assert os.environ["DATABASE_URL"] == "postgresql+psycopg2://u:p@host:5432/db"
        assert os.environ["TRAMEX_FERNET_KEY"] == "una-llave"

    def test_el_entorno_real_tiene_prioridad_sobre_el_archivo(self, tmp_path, monkeypatch):
        """
        Es lo que permite que el mismo comando sirva en local y en un contenedor.

        En local lee el `.env`; en despliegue recibe secretos inyectados que no
        deben quedar pisados por un archivo olvidado en la imagen.
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
