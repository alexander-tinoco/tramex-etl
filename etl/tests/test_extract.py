"""
Tests for the extraction phase.

The test Excel files are generated on the fly: the real file contains
clients' personal data and can't be versioned, but its *structure* can be
reproduced, including the quirks that motivate it (four title rows before
the header, extra spaces in column names).
"""

from __future__ import annotations

import pandas as pd
import pytest

from etl.helpers.extract import (
    HOJAS,
    HOJAS_POR_TABLA,
    ErrorDeEstructura,
    leer_archivo,
    leer_hoja,
)


def escribir_libro(ruta, hojas: dict[str, pd.DataFrame], fila_inicio_master: int = 4) -> None:
    """Writes a workbook with the structure of the real operational file."""
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        for nombre, marco in hojas.items():
            inicio = fila_inicio_master if nombre == "Master Tramex" else 0
            marco.to_excel(escritor, sheet_name=nombre, index=False, startrow=inicio)


@pytest.fixture(name="hojas_validas")
def hojas_validas_fixture() -> dict[str, pd.DataFrame]:
    return {
        "Master Tramex": pd.DataFrame(
            {
                "NOMBRE": ["Jorge Monroy"],
                "ID ": ["SOL001"],
                "Telefono": ["4471148272"],
                "N°Pasaporte ": ["G111"],
                "TRAMITE": ["VISA B1/B2"],
                "CITA ": ["Renovacion"],
                "Correo electrónico": ["jorge@example.com"],
                "CONTRASEÑA": ["clave"],
            }
        ),
        "Global entry": pd.DataFrame(
            {
                "Nombre": ["Ana"],
                "Apellido ": ["Lopez"],
                "Correo electrónico": ["ana@example.com"],
                "Número de pasaporte": ["G222"],
                "Número de la cuenta": ["clave-ge"],
            }
        ),
        "Pasaportes": pd.DataFrame(
            {
                "Nombre": ["Carlos"],
                "Apellido ": ["Gomez"],
                "Teléfono": ["5551234567"],
                "Lugar de la cita": ["CDMX"],
                "Fecha Cita": ["15/08/2026"],
            }
        ),
        "Canada": pd.DataFrame(
            {
                "NOMBRE": ["Maria Diaz"],
                "Cuenta IRCC": ["IRCC-1"],
                "Telefono": ["9998887776"],
                "N°Pasaporte ": ["C111"],
                "Cuenta Cita": ["clave-ca"],
            }
        ),
    }


class TestLeerHoja:
    def test_salta_las_filas_de_titulos_de_la_hoja_principal(self, tmp_path, hojas_validas):
        """
        "Master Tramex"'s real header lives on the fifth row.

        This is the quirk that forces the header row to be configured per
        sheet: reading from the first row would name every column "Unnamed".
        """
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        marco = leer_hoja(ruta, HOJAS_POR_TABLA["master_tramex"])

        assert list(marco.columns) == [
            "nombre",
            "id_solicitud",
            "telefono",
            "numero_pasaporte",
            "tramite",
            "cita",
            "correo_electronico",
            "contrasena",
        ]
        assert marco.iloc[0]["nombre"] == "Jorge Monroy"

    def test_tolera_espacios_y_mayusculas_en_los_encabezados(self, tmp_path, hojas_validas):
        """
        Column names change between revisions of the file.

        Matching them exactly would break the pipeline because someone
        deleted a trailing space while editing the sheet.
        """
        hojas_validas["Canada"] = hojas_validas["Canada"].rename(
            columns={"NOMBRE": " nombre ", "Cuenta IRCC": "CUENTA IRCC"}
        )
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        marco = leer_hoja(ruta, HOJAS_POR_TABLA["canada"])
        assert marco.iloc[0]["nombre"] == "Maria Diaz"
        assert marco.iloc[0]["cuenta_ircc"] == "IRCC-1"

    def test_una_columna_ausente_detiene_la_carga(self, tmp_path, hojas_validas):
        """
        Failing is preferable to loading thousands of rows with an empty field.

        If someone renames "CONTRASEÑA", proceeding would save every record
        with no credential and nobody would notice until they needed it.
        """
        hojas_validas["Master Tramex"] = hojas_validas["Master Tramex"].drop(columns=["CONTRASEÑA"])
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        with pytest.raises(ErrorDeEstructura, match="CONTRASEÑA"):
            leer_hoja(ruta, HOJAS_POR_TABLA["master_tramex"])

    def test_el_error_menciona_los_encabezados_encontrados(self, tmp_path, hojas_validas):
        """So the operator can compare without opening the file."""
        hojas_validas["Canada"] = hojas_validas["Canada"].drop(columns=["Cuenta Cita"])
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        with pytest.raises(ErrorDeEstructura) as excepcion:
            leer_hoja(ruta, HOJAS_POR_TABLA["canada"])
        assert "Cuenta IRCC" in str(excepcion.value)


class TestLeerArchivo:
    def test_lee_las_cuatro_hojas(self, tmp_path, hojas_validas):
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        marcos = leer_archivo(ruta)
        assert set(marcos) == {"master_tramex", "global_entry", "pasaportes", "canada"}
        assert all(len(marco) == 1 for marco in marcos.values())

    def test_puede_procesar_un_subconjunto(self, tmp_path, hojas_validas):
        ruta = tmp_path / "TRAMEX.xlsx"
        escribir_libro(ruta, hojas_validas)

        marcos = leer_archivo(ruta, ("pasaportes",))
        assert set(marcos) == {"pasaportes"}

    def test_un_archivo_inexistente_se_reporta_con_claridad(self, tmp_path):
        with pytest.raises(ErrorDeEstructura, match="does not exist"):
            leer_archivo(tmp_path / "no-esta.xlsx")


def test_la_configuracion_cubre_las_cuatro_tablas():
    assert {hoja.tabla_destino for hoja in HOJAS} == {
        "master_tramex",
        "global_entry",
        "pasaportes",
        "canada",
    }
