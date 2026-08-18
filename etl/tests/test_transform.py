"""
Pruebas de la fase de transformacion.

Se construyen DataFrames a mano en lugar de leer un Excel: la transformacion es
pura y debe poder probarse sin el archivo real, que ademas contiene datos
personales y no puede versionarse.
"""

import pandas as pd
import pytest

from etl.helpers.transform import limpiar_registro, proyectar_clientes, transformar
from tramex_shared import calcular_clave_natural


def test_limpia_cada_campo_con_su_limpiador():
    resultado = limpiar_registro(
        {
            "nombre": "  Jorge   Monroy ",
            "telefono": "(447) 114-8272",
            "correo_electronico": "  Jorge@Example.COM ",
            "numero_pasaporte": "g33 961340",
        }
    )
    assert resultado == {
        "nombre": "Jorge Monroy",
        "telefono": "4471148272",
        "correo_electronico": "jorge@example.com",
        "numero_pasaporte": "G33961340",
    }


def test_descarta_filas_sin_nombre():
    """En el archivo de origen las filas sin nombre son separadores y totales."""
    marco = pd.DataFrame(
        {
            "nombre": ["Ana Lopez", None, "   ", "Jorge Monroy"],
            "numero_pasaporte": ["G1", "G2", "G3", "G4"],
            "id_solicitud": ["S1", "S2", "S3", "S4"],
            "telefono": [None, None, None, None],
            "tramite": [None, None, None, None],
            "cita": [None, None, None, None],
            "correo_electronico": [None, None, None, None],
            "contrasena": [None, None, None, None],
        }
    )
    registros = transformar("master_tramex", marco)
    assert [r["nombre"] for r in registros] == ["Ana Lopez", "Jorge Monroy"]


def test_calcula_clave_natural_y_hash_por_registro():
    marco = pd.DataFrame(
        {
            "nombre": ["Ana Lopez"],
            "numero_pasaporte": ["G222"],
            "id_solicitud": ["SOL1"],
            "telefono": ["5550001111"],
            "tramite": ["VISA F1"],
            "cita": [None],
            "correo_electronico": ["ana@example.com"],
            "contrasena": ["secreta"],
        }
    )
    registro = transformar("master_tramex", marco)[0]

    assert registro["clave_natural"] == calcular_clave_natural(
        "master_tramex", ["Ana Lopez", "G222", "SOL1"]
    )
    assert len(registro["hash_fila"]) == 64


def test_el_hash_cambia_cuando_cambia_la_contrasena():
    """
    La credencial participa del hash en texto plano.

    Si no lo hiciera, cambiar solo la contrasena en el archivo no se detectaria
    como novedad y la carga nunca la actualizaria.
    """

    def construir(contrasena):
        marco = pd.DataFrame(
            {
                "nombre": ["Ana Lopez"],
                "numero_pasaporte": ["G222"],
                "id_solicitud": ["SOL1"],
                "telefono": [None],
                "tramite": [None],
                "cita": [None],
                "correo_electronico": [None],
                "contrasena": [contrasena],
            }
        )
        return transformar("master_tramex", marco)[0]

    original = construir("clave-vieja")
    modificado = construir("clave-nueva")

    assert original["clave_natural"] == modificado["clave_natural"]
    assert original["hash_fila"] != modificado["hash_fila"]


def test_colapsa_duplicados_dentro_del_mismo_archivo():
    """Dos capturas de la misma persona con distinto espaciado son una sola fila."""
    marco = pd.DataFrame(
        {
            "nombre": ["José Ramírez", "  jose   ramirez ", "Ana Lopez"],
            "numero_pasaporte": ["G111", "G111", "G222"],
            "id_solicitud": ["S1", "S1", "S2"],
            "telefono": [None, None, None],
            "tramite": [None, None, None],
            "cita": [None, None, None],
            "correo_electronico": [None, None, None],
            "contrasena": [None, None, None],
        }
    )
    registros = transformar("master_tramex", marco)
    assert len(registros) == 2


def test_pasaportes_separa_fecha_valida_de_texto_libre():
    marco = pd.DataFrame(
        {
            "nombre": ["Ana", "Lucia"],
            "apellido": ["Lopez", "Diaz"],
            "telefono": [None, None],
            "lugar_cita": ["CDMX", "GDL"],
            "fecha_cita_cruda": ["15/08/2026", "MARZO"],
        }
    )
    registros = transformar("pasaportes", marco)
    por_nombre = {r["nombre"]: r for r in registros}

    assert str(por_nombre["Ana"]["fecha_cita"]) == "2026-08-15"
    assert por_nombre["Ana"]["fecha_cita_original"] is None

    assert por_nombre["Lucia"]["fecha_cita"] is None
    assert por_nombre["Lucia"]["fecha_cita_original"] == "MARZO"


def test_transformar_es_determinista():
    """Dos corridas sobre la misma entrada producen exactamente lo mismo."""
    marco = pd.DataFrame(
        {
            "nombre": ["Ana Lopez"],
            "cuenta_ircc": ["IRCC-1"],
            "telefono": ["5550001111"],
            "numero_pasaporte": ["G222"],
            "contrasena": ["secreta"],
        }
    )
    assert transformar("canada", marco) == transformar("canada", marco.copy())


def test_proyecta_los_datos_de_persona_de_cada_tramite():
    proyecciones = proyectar_clientes(
        {
            "master_tramex": [{"nombre": "Ana Lopez", "numero_pasaporte": "G222"}],
            "pasaportes": [{"nombre": "Ana", "apellido": "Lopez"}],
        }
    )
    assert len(proyecciones) == 2
    assert proyecciones[0]["nombre"] == "Ana Lopez"
    assert proyecciones[1]["apellido"] == "Lopez"


@pytest.mark.parametrize("tabla", ["master_tramex", "global_entry", "pasaportes", "canada"])
def test_un_marco_vacio_no_rompe_la_transformacion(tabla):
    assert transformar(tabla, pd.DataFrame({"nombre": []})) == []
