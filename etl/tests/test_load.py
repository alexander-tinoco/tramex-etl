"""
Pruebas de la fase de carga.

Aqui se verifica la propiedad que motivo la reescritura del pipeline: que
reprocesar el mismo archivo no duplique nada. La version anterior usaba
`to_sql(..., if_exists="append")` y duplicaba la base entera en cada corrida.
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
        # La comprobacion que importa: sigue habiendo una sola fila.
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
        Fernet produce un criptograma distinto en cada llamada.

        Si la carga reescribiera filas sin novedades, el criptograma cambiaria
        en cada corrida sin que el dato haya cambiado, ensuciando el historial
        y desperdiciando escrituras.
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
        La hoja de Pasaportes no captura pasaporte ni correo.

        Sin la segunda pasada de resolucion quedaria desconectada del resto de
        los tramites de la misma persona.
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
        Ante ambiguedad se prefiere separar.

        Unir despues dos expedientes que quedaron sueltos es trivial; separar
        dos que se fusionaron por error, no.
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

        # Dos personas identificables mas una tercera ambigua que no se fusiona.
        assert _contar(engine, "clientes") == 3


class TestTransaccionalidad:
    def test_un_fallo_a_mitad_de_carga_no_deja_datos_parciales(self, engine, fernet, monkeypatch):
        """
        La version anterior cargaba hoja por hoja sin transaccion.

        Un fallo en la tercera hoja dejaba las dos primeras escritas, lo que
        obligaba a limpiar a mano antes de reintentar.
        """
        import etl.helpers.load as modulo_load

        upsert_original = modulo_load._upsert
        llamadas = {"n": 0}

        def upsert_que_falla(conexion, tabla, registros, tamano_lote):
            llamadas["n"] += 1
            # Falla al escribir la segunda tabla de tramite, ya con clientes y
            # la primera tabla escritas dentro de la transaccion.
            if llamadas["n"] == 3:
                raise RuntimeError("fallo simulado a mitad de la carga")
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

        # Nada quedo escrito: ni clientes, ni la tabla que si alcanzo a cargarse.
        assert _contar(engine, "clientes") == 0
        assert _contar(engine, "master_tramex") == 0
        assert _contar(engine, "canada") == 0

    def test_la_simulacion_no_escribe_nada(self, engine, fernet):
        resumen = _cargar(engine, fernet, {"master_tramex": _marco_master()}, simulacion=True)

        assert resumen.simulacion is True
        # El resumen informa lo que habria pasado...
        assert resumen.por_tabla["master_tramex"].insertados == 1
        # ...pero la base sigue vacia.
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
        # El registro anterior no se destruye, solo se archiva.
        assert _contar(engine, "master_tramex") == 2

    def test_un_modo_desconocido_se_rechaza(self, engine, fernet):
        with pytest.raises(ErrorDeCarga, match="Modo de carga desconocido"):
            _cargar(engine, fernet, {"master_tramex": _marco_master()}, modo="inventado")


def test_reflejar_tablas_falla_con_mensaje_util_si_faltan_migraciones(fernet):
    from sqlalchemy import create_engine

    vacio = create_engine("sqlite:///:memory:")
    with pytest.raises(ErrorDeCarga, match="migraciones"):
        reflejar_tablas(vacio)
