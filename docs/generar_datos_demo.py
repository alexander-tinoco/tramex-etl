#!/usr/bin/env python3
"""
Genera un archivo Excel sintetico con la estructura del archivo operativo real.

Existe para poder poblar una demostracion, tomar capturas de pantalla y probar
el pipeline sin tocar datos personales. El archivo real contiene nombres,
telefonos, correos, numeros de pasaporte y contrasenas de cuentas de clientes,
y nunca debe salir del entorno de la agencia.

Reproduce tambien las rarezas del original, porque son justamente las que el
pipeline tiene que saber manejar:

* La hoja principal arrastra cuatro filas de titulos antes del encabezado real.
* Hay filas de relleno y de totales sin nombre.
* La misma persona aparece capturada dos veces con distinto espaciado.
* La columna de fecha mezcla fechas validas con texto libre ("MARZO").
* Los telefonos vienen con formatos heterogeneos.

Uso:
    python docs/generar_datos_demo.py raw-data/TRAMEX_demo.xlsx
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

#: Semilla fija para que el archivo sea reproducible entre ejecuciones.
SEMILLA = 2026

NOMBRES = [
    "Ana",
    "Jorge",
    "Maria",
    "Carlos",
    "Lucia",
    "Miguel",
    "Sofia",
    "Ricardo",
    "Valeria",
    "Fernando",
    "Camila",
    "Andres",
    "Daniela",
    "Roberto",
    "Paola",
    "Alejandro",
    "Gabriela",
    "Sergio",
    "Natalia",
    "Eduardo",
]
APELLIDOS = [
    "Ramirez",
    "Monroy",
    "Lopez",
    "Gomez",
    "Diaz",
    "Hernandez",
    "Torres",
    "Vargas",
    "Castillo",
    "Mendoza",
    "Rojas",
    "Guerrero",
    "Navarro",
    "Peralta",
]
TRAMITES = ["VISA B1/B2", "VISA F1", "RENOVACION", "VISA H2B"]
LUGARES = ["CDMX", "Guadalajara", "Monterrey", "Tijuana", "Merida"]
TEXTO_LIBRE_FECHAS = ["MARZO", "pendiente", "por confirmar", "ya fue"]


def _personas(cantidad: int, azar: random.Random) -> list[dict[str, str]]:
    """Construye un conjunto estable de personas ficticias."""
    personas = []
    for indice in range(1, cantidad + 1):
        nombre = azar.choice(NOMBRES)
        apellido = azar.choice(APELLIDOS)
        personas.append(
            {
                "nombre": nombre,
                "apellido": apellido,
                "completo": f"{nombre} {apellido}",
                "pasaporte": f"G{indice:08d}",
                # example.com esta reservado para documentacion, asi que ningun
                # correo generado aqui puede corresponder a un buzon real.
                "correo": f"{nombre.lower()}.{apellido.lower()}{indice}@example.com",
                "telefono": azar.choice(
                    [
                        f"(44{indice % 10}) 114-{indice:04d}",
                        f"55{indice:08d}",
                        f"+52 33 {indice:07d}",
                    ]
                ),
            }
        )
    return personas


def construir(destino: Path, total_personas: int = 140) -> None:
    azar = random.Random(SEMILLA)
    personas = _personas(total_personas, azar)

    master = pd.DataFrame(
        {
            "NOMBRE": [p["completo"] for p in personas],
            "ID ": [f"SOL{i:05d}" for i in range(1, len(personas) + 1)],
            "Telefono": [p["telefono"] for p in personas],
            "N°Pasaporte ": [p["pasaporte"] for p in personas],
            "TRAMITE": [azar.choice(TRAMITES) for _ in personas],
            "CITA ": [azar.choice(["Pendiente", "Agendada", "Completada", None]) for _ in personas],
            "Correo electrónico": [p["correo"] for p in personas],
            "CONTRASEÑA": [f"Cuenta{i:04d}!" for i in range(1, len(personas) + 1)],
        }
    )
    # Filas de relleno y totales, tal como aparecen en el archivo real.
    master.loc[len(master)] = [None] * 8
    master.loc[len(master)] = [None, "TOTAL", None, None, None, None, None, None]
    # La misma persona capturada de nuevo con otro espaciado y capitalizacion:
    # el pipeline debe reconocerla como una sola.
    primera = personas[0]
    master.loc[len(master)] = [
        f"  {primera['completo'].lower()}  ",
        "SOL00001",
        primera["telefono"],
        primera["pasaporte"].lower(),
        master.loc[0, "TRAMITE"],
        master.loc[0, "CITA "],
        primera["correo"],
        "Cuenta0001!",
    ]

    subconjunto_global = personas[: int(total_personas * 0.4)]
    global_entry = pd.DataFrame(
        {
            "Nombre": [p["nombre"] for p in subconjunto_global],
            "Apellido ": [p["apellido"] for p in subconjunto_global],
            "Correo electrónico": [p["correo"] for p in subconjunto_global],
            "Número de pasaporte": [p["pasaporte"] for p in subconjunto_global],
            "Número de la cuenta": [f"GE-{i:05d}" for i in range(1, len(subconjunto_global) + 1)],
        }
    )

    # La hoja de pasaportes no captura pasaporte ni correo: es el caso que
    # obliga a resolver la identidad por nombre.
    subconjunto_pasaportes = personas[: int(total_personas * 0.55)]
    pasaportes = pd.DataFrame(
        {
            "Nombre": [p["nombre"] for p in subconjunto_pasaportes],
            "Apellido ": [p["apellido"] for p in subconjunto_pasaportes],
            "Teléfono": [p["telefono"] for p in subconjunto_pasaportes],
            "Lugar de la cita": [azar.choice(LUGARES) for _ in subconjunto_pasaportes],
            "Fecha Cita": [
                f"{azar.randint(1, 28):02d}/{azar.randint(1, 12):02d}/2026"
                if indice % 3
                else azar.choice(TEXTO_LIBRE_FECHAS)
                for indice in range(len(subconjunto_pasaportes))
            ],
        }
    )

    subconjunto_canada = personas[: int(total_personas * 0.3)]
    canada = pd.DataFrame(
        {
            "NOMBRE": [p["completo"] for p in subconjunto_canada],
            "Cuenta IRCC": [f"IRCC-{i:06d}" for i in range(1, len(subconjunto_canada) + 1)],
            "Telefono": [p["telefono"] for p in subconjunto_canada],
            "N°Pasaporte ": [p["pasaporte"] for p in subconjunto_canada],
            "Cuenta Cita": [f"Ircc{i:04d}!" for i in range(1, len(subconjunto_canada) + 1)],
        }
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        # startrow=4 reproduce las cuatro filas de titulos de la hoja principal.
        master.to_excel(escritor, sheet_name="Master Tramex", index=False, startrow=4)
        global_entry.to_excel(escritor, sheet_name="Global entry", index=False)
        pasaportes.to_excel(escritor, sheet_name="Pasaportes", index=False)
        canada.to_excel(escritor, sheet_name="Canada", index=False)

    print(f"Archivo sintetico generado en {destino}")
    print(f"  Master Tramex : {len(master)} filas (incluye relleno y duplicado)")
    print(f"  Global entry  : {len(global_entry)} filas")
    print(f"  Pasaportes    : {len(pasaportes)} filas")
    print(f"  Canada        : {len(canada)} filas")


if __name__ == "__main__":
    ruta = Path(sys.argv[1] if len(sys.argv) > 1 else "raw-data/TRAMEX_demo.xlsx")
    construir(ruta)
