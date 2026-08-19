"""
Tests for the load phase.

This is where the property that motivated the pipeline's rewrite gets
verified: that reprocessing the same file duplicates nothing. The previous
version used `to_sql(..., if_exists="append")` and duplicated the entire
database on every run.
"""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import func, select, text

from etl.helpers.load import ErrorDeCarga, cargar, reflejar_tablas
from etl.helpers.transform import transformar


def _marco_master(nombre="Jorge Monroy", pasaporte="G111", contrasena="Secreta123", cita=None):
    return pd.DataFrame(
        {
            "nombre": [nombre],
            "id_solicitud": ["SOL777"],
            "telefono": ["4471148272"],
            "numero_pasaporte": [pasaporte],
            "tramite": ["VISA B1/B2"],
            "cita": [cita],
            "correo_electronico": ["jorge@example.com"],
            "contrasena": [contrasena],
        }
    )


def _contar(engine, tabla):
    with engine.connect() as conexion:
        return conexion.scalar(select(func.count()).select_from(text(tabla)))


def _cargar(engine, fernet, marcos, **kwargs):
    registros = {tabla: transformar(tabla, marco) for tabla, marco in marcos.items()}
    return cargar(engine, registros, fernet=fernet, **kwargs)


class TestIdempotencia:
    def test_reprocesar_el_mismo_archivo_no_duplica(self, engine, fernet):
        marcos = {"master_tramex": _marco_master()}

        primera = _cargar(engine, fernet, marcos)
        assert primera.por_tabla["master_tramex"].insertados == 1
        assert _contar(engine, "master_tramex") == 1

        segunda = _cargar(engine, fernet, marcos)
        assert segunda.por_tabla["master_tramex"].insertados == 0
        assert segunda.por_tabla["master_tramex"].sin_cambios == 1
        assert segunda.hubo_cambios is False
        # The check that matters: there's still only one row.
        assert _contar(engine, "master_tramex") == 1

    def test_tres_corridas_seguidas_dejan_el_mismo_estado(self, engine, fernet):
        marcos = {"master_tramex": _marco_master()}
        for _ in range(3):
            _cargar(engine, fernet, marcos)
        assert _contar(engine, "master_tramex") == 1
        assert _contar(engine, "clientes") == 1

    def test_un_cambio_real_si_se_aplica(self, engine, fernet):
        _cargar(engine, fernet, {"master_tramex": _marco_master(cita="Pendiente")})
        resumen = _cargar(engine, fernet, {"master_tramex": _marco_master(cita="2026-09-01")})

        assert resumen.por_tabla["master_tramex"].actualizados == 1
        assert _contar(engine, "master_tramex") == 1

        tablas = reflejar_tablas(engine)
        with engine.connect() as conexion:
            assert conexion.scalar(select(tablas["master_tramex"].c.cita)) == "2026-09-01"

    def test_una_fila_sin_cambios_no_vuelve_a_cifrar_la_credencial(self, engine, fernet):
        """
        Fernet produces a different ciphertext on every call.

        If the load rewrote unchanged rows, the ciphertext would change on
        every run even though the data hadn't, polluting the history and
        wasting writes.
        """
        marcos = {"master_tramex": _marco_master()}
        tablas = reflejar_tablas(engine)

        _cargar(engine, fernet, marcos)
        with engine.connect() as conexion:
            criptograma_inicial = conexion.scalar(
                select(tablas["master_tramex"].c.contrasena_cifrada)
            )

        _cargar(engine, fernet, marcos)
        with engine.connect() as conexion:
            criptograma_final = conexion.scalar(
                select(tablas["master_tramex"].c.contrasena_cifrada)
            )

        assert criptograma_inicial == criptograma_final

    def test_cambiar_la_contrasena_si_regenera_el_criptograma(self, engine, fernet):
        tablas = reflejar_tablas(engine)

        _cargar(engine, fernet, {"master_tramex": _marco_master(contrasena="vieja")})
        _cargar(engine, fernet, {"master_tramex": _marco_master(contrasena="nueva")})

        with engine.connect() as conexion:
            criptograma = conexion.scalar(select(tablas["master_tramex"].c.contrasena_cifrada))
        assert fernet.decrypt(criptograma.encode()).decode() == "nueva"


class TestCifrado:
    def test_la_credencial_nunca_se_guarda_en_claro(self, engine, fernet):
        _cargar(engine, fernet, {"master_tramex": _marco_master(contrasena="SuperSecreta")})

        tablas = reflejar_tablas(engine)
        with engine.connect() as conexion:
            fila = conexion.execute(select(tablas["master_tramex"])).mappings().one()

        assert "SuperSecreta" not in str(dict(fila))
        assert fernet.decrypt(fila["contrasena_cifrada"].encode()).decode() == "SuperSecreta"

    def test_una_fila_sin_credencial_guarda_nulo(self, engine, fernet):
        _cargar(engine, fernet, {"master_tramex": _marco_master(contrasena=None)})

        tablas = reflejar_tablas(engine)
        with engine.connect() as conexion:
            assert conexion.scalar(select(tablas["master_tramex"].c.contrasena_cifrada)) is None


class TestResolucionDeClientes:
    def test_la_misma_persona_en_dos_hojas_produce_un_solo_cliente(self, engine, fernet):
        marcos = {
            "master_tramex": _marco_master(nombre="José Ramírez", pasaporte="G111"),
            "canada": pd.DataFrame(
                {
                    "nombre": ["José Ramírez"],
                    "cuenta_ircc": ["IRCC-9"],
                    "telefono": ["4471148272"],
                    "numero_pasaporte": ["G111"],
                    "contrasena": [None],
                }
            ),
        }
        _cargar(engine, fernet, marcos)

        assert _contar(engine, "clientes") == 1

        tablas = reflejar_tablas(engine)
        with engine.connect() as conexion:
            ids = set(conexion.scalars(select(tablas["master_tramex"].c.cliente_id)).all()) | set(
                conexion.scalars(select(tablas["canada"].c.cliente_id)).all()
            )
        assert len(ids) == 1

    def test_una_hoja_sin_identificador_duro_se_engancha_por_nombre(self, engine, fernet):
        """
        The Pasaportes sheet captures neither passport nor email.

        Without the second resolution pass it would end up disconnected from
        the same person's other tramites.
        """
        marcos = {
            "global_entry": pd.DataFrame(
                {
                    "nombre": ["Ana"],
                    "apellido": ["Lopez"],
                    "correo_electronico": ["ana@example.com"],
                    "numero_pasaporte": ["G222"],
                    "contrasena": [None],
                }
            ),
            "pasaportes": pd.DataFrame(
                {
                    "nombre": ["Ana"],
                    "apellido": ["Lopez"],
                    "telefono": ["5550001111"],
                    "lugar_cita": ["CDMX"],
                    "fecha_cita_cruda": ["MARZO"],
                }
            ),
        }
        _cargar(engine, fernet, marcos)

        assert _contar(engine, "clientes") == 1

    def test_dos_homonimos_sin_identificador_no_se_fusionan(self, engine, fernet):
        """
        Faced with ambiguity, keeping records separate is preferred.

        Merging two records that were left separate later is trivial;
        splitting two that were merged by mistake is not.
        """
        marcos = {
            "global_entry": pd.DataFrame(
                {
                    "nombre": ["Ana", "Ana"],
                    "apellido": ["Lopez", "Lopez"],
                    "correo_electronico": ["ana1@example.com", "ana2@example.com"],
                    "numero_pasaporte": ["G1", "G2"],
                    "contrasena": [None, None],
                }
            ),
            "pasaportes": pd.DataFrame(
                {
                    "nombre": ["Ana"],
                    "apellido": ["Lopez"],
                    "telefono": [None],
                    "lugar_cita": ["CDMX"],
                    "fecha_cita_cruda": [None],
                }
            ),
        }
        _cargar(engine, fernet, marcos)

        # Two identifiable people plus a third, ambiguous one that isn't merged.
        assert _contar(engine, "clientes") == 3


class TestTransaccionalidad:
    def test_un_fallo_a_mitad_de_carga_no_deja_datos_parciales(self, engine, fernet, monkeypatch):
        """
        The previous version loaded sheet by sheet with no transaction.

        A failure on the third sheet left the first two written, which
        forced a manual cleanup before retrying.
        """
        import etl.helpers.load as modulo_load

        upsert_original = modulo_load._upsert
        llamadas = {"n": 0}

        def upsert_que_falla(conexion, tabla, registros, tamano_lote):
            llamadas["n"] += 1
            # Fails while writing the second tramite table, with clients and
            # the first table already written inside the transaction.
            if llamadas["n"] == 3:
                raise RuntimeError("simulated failure halfway through the load")
            return upsert_original(conexion, tabla, registros, tamano_lote)

        monkeypatch.setattr(modulo_load, "_upsert", upsert_que_falla)

        marcos = {
            "master_tramex": _marco_master(),
            "canada": pd.DataFrame(
                {
                    "nombre": ["Maria"],
                    "cuenta_ircc": ["IRCC-1"],
                    "telefono": [None],
                    "numero_pasaporte": ["C1"],
                    "contrasena": [None],
                }
            ),
        }

        with pytest.raises(RuntimeError):
            _cargar(engine, fernet, marcos)

        # Nothing was written: not clients, not the table that did get to load.
        assert _contar(engine, "clientes") == 0
        assert _contar(engine, "master_tramex") == 0
        assert _contar(engine, "canada") == 0

    def test_la_simulacion_no_escribe_nada(self, engine, fernet):
        resumen = _cargar(engine, fernet, {"master_tramex": _marco_master()}, simulacion=True)

        assert resumen.simulacion is True
        # The summary reports what would have happened...
        assert resumen.por_tabla["master_tramex"].insertados == 1
        # ...but the database is still empty.
        assert _contar(engine, "master_tramex") == 0
        assert _contar(engine, "clientes") == 0


class TestModos:
    def test_modo_reemplazar_archiva_lo_vigente(self, engine, fernet):
        _cargar(engine, fernet, {"master_tramex": _marco_master(nombre="Antiguo", pasaporte="A1")})
        _cargar(
            engine,
            fernet,
            {"master_tramex": _marco_master(nombre="Nuevo", pasaporte="N1")},
            modo="reemplazar",
        )

        tablas = reflejar_tablas(engine)
        with engine.connect() as conexion:
            activos = conexion.scalars(
                select(tablas["master_tramex"].c.nombre).where(
                    tablas["master_tramex"].c.eliminado_en.is_(None)
                )
            ).all()

        assert activos == ["Nuevo"]
        # The previous record isn't destroyed, only archived.
        assert _contar(engine, "master_tramex") == 2

    def test_un_modo_desconocido_se_rechaza(self, engine, fernet):
        with pytest.raises(ErrorDeCarga, match="Unknown load mode"):
            _cargar(engine, fernet, {"master_tramex": _marco_master()}, modo="inventado")


def test_reflejar_tablas_falla_con_mensaje_util_si_faltan_migraciones(fernet):
    from sqlalchemy import create_engine

    vacio = create_engine("sqlite:///:memory:")
    with pytest.raises(ErrorDeCarga, match="migrations"):
        reflejar_tablas(vacio)
