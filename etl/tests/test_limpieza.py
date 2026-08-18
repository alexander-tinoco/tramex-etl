"""
Pruebas de las funciones de limpieza.

Los casos no son inventados: reproducen la suciedad real del archivo operativo
(telefonos con formato libre, celdas de fecha con texto, correos multiples en
una sola celda, centinelas de vacio escritos a mano).
"""

from datetime import date, datetime

import pytest

from etl.helpers.limpieza import (
    limpiar_correo,
    limpiar_pasaporte,
    limpiar_telefono,
    limpiar_texto,
    parsear_fecha,
)


class TestLimpiarTexto:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("  Jorge Monroy  ", "Jorge Monroy"),
            ("Jorge   Ulices    Monroy", "Jorge Ulices Monroy"),
            ("Ana", "Ana"),
        ],
    )
    def test_recorta_y_colapsa_espacios(self, entrada, esperado):
        assert limpiar_texto(entrada) == esperado

    @pytest.mark.parametrize("entrada", ["", "   ", None, float("nan"), "N/A", "-", "sin dato"])
    def test_los_vacios_y_centinelas_se_vuelven_nulos(self, entrada):
        assert limpiar_texto(entrada) is None


class TestLimpiarTelefono:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("(447) 114-8272", "4471148272"),
            ("447 114 8272", "4471148272"),
            ("+52 55 1234 5678", "525512345678"),
            ("447-114-8272 ext 5", "44711482725"),
            # Los telefonos leidos como numero llegan con decimal flotante.
            (4471148272.0, "4471148272"),
        ],
    )
    def test_conserva_solo_digitos(self, entrada, esperado):
        assert limpiar_telefono(entrada) == esperado

    @pytest.mark.parametrize("entrada", ["sin telefono", "", None, "---"])
    def test_sin_digitos_devuelve_nulo(self, entrada):
        assert limpiar_telefono(entrada) is None

    def test_no_asume_longitud_fija(self):
        """El archivo mezcla numeros locales e internacionales a proposito."""
        assert limpiar_telefono("5512345678") == "5512345678"
        assert limpiar_telefono("+1 (305) 555 0199") == "13055550199"


class TestLimpiarCorreo:
    def test_normaliza_a_minusculas(self):
        assert limpiar_correo("  Jorge@Example.COM ") == "jorge@example.com"

    def test_toma_el_primero_cuando_la_celda_trae_varios(self):
        """Una celda con dos correos no debe descartarse entera."""
        assert limpiar_correo("uno@example.com, dos@example.com") == "uno@example.com"

    @pytest.mark.parametrize(
        "entrada",
        ["no tiene correo", "arroba example com", "@example.com", "usuario@", "", None],
    )
    def test_descarta_lo_que_no_es_correo(self, entrada):
        assert limpiar_correo(entrada) is None


class TestLimpiarPasaporte:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("g33 961340", "G33961340"),
            ("G-33961340", "G33961340"),
            ("  g33961340  ", "G33961340"),
        ],
    )
    def test_converge_variantes_del_mismo_numero(self, entrada, esperado):
        """
        Es el identificador del que depende la resolucion de identidad.

        Si "g33 961340" y "G33961340" no convergieran, la misma persona se
        partiria en dos clientes distintos.
        """
        assert limpiar_pasaporte(entrada) == esperado


class TestParsearFecha:
    @pytest.mark.parametrize(
        ("entrada", "esperado"),
        [
            ("15/08/2026", date(2026, 8, 15)),
            ("2026-08-15", date(2026, 8, 15)),
            ("15-08-2026", date(2026, 8, 15)),
            (datetime(2026, 8, 15, 10, 30), date(2026, 8, 15)),
            (date(2026, 8, 15), date(2026, 8, 15)),
        ],
    )
    def test_reconoce_los_formatos_del_archivo(self, entrada, esperado):
        fecha, original = parsear_fecha(entrada)
        assert fecha == esperado
        assert original is None

    @pytest.mark.parametrize("entrada", ["MARZO", "pendiente", "ya fue", "proxima semana"])
    def test_preserva_el_texto_libre_en_vez_de_descartarlo(self, entrada):
        """
        Perder estas celdas seria perder informacion que la operadora si usa.

        El contrato es explicito: o hay fecha, o hay texto original, nunca ambos.
        """
        fecha, original = parsear_fecha(entrada)
        assert fecha is None
        assert original == entrada

    @pytest.mark.parametrize("entrada", [None, "", "   ", float("nan")])
    def test_los_vacios_no_producen_ni_fecha_ni_texto(self, entrada):
        assert parsear_fecha(entrada) == (None, None)
