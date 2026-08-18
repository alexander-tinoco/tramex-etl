"""
Pruebas del CRUD de los cuatro recursos de tramite.

Los cuatro se generan con la misma fabrica, asi que el comportamiento comun se
ejercita de forma parametrizada en vez de repetir el mismo bloque cuatro veces.
Lo especifico de cada recurso (campos propios, presencia o ausencia de
credencial) se prueba aparte.
"""

from datetime import UTC

import pytest

RECURSOS = {
    "master-tramex": {
        "payload": {
            "nombre": "Jorge Monroy",
            "id_solicitud": "SOL777",
            "telefono": "4471148272",
            "numero_pasaporte": "G33961340",
            "tramite": "VISA B1/B2",
            "cita": "Renovacion",
            "correo_electronico": "jorge@example.com",
            "contrasena": "SuperPassword123",
        },
        "tiene_credencial": True,
    },
    "global-entry": {
        "payload": {
            "nombre": "Ana",
            "apellido": "Lopez",
            "correo_electronico": "ana@example.com",
            "numero_pasaporte": "PAS987",
            "contrasena": "globalSecret",
        },
        "tiene_credencial": True,
    },
    "pasaportes": {
        "payload": {
            "nombre": "Carlos",
            "apellido": "Gomez",
            "telefono": "5551234567",
            "lugar_cita": "CDMX",
            "fecha_cita": "2026-08-15",
        },
        "tiene_credencial": False,
    },
    "canada": {
        "payload": {
            "nombre": "Maria",
            "cuenta_ircc": "IRCC444",
            "telefono": "9998887776",
            "numero_pasaporte": "CAN1122",
            "contrasena": "canadaPass",
        },
        "tiene_credencial": True,
    },
}

IDS = list(RECURSOS)


@pytest.fixture(params=IDS)
def recurso(request):
    """Cada prueba parametrizada recibe el nombre del recurso y su carga util."""
    nombre = request.param
    return nombre, dict(RECURSOS[nombre]["payload"]), RECURSOS[nombre]["tiene_credencial"]


def test_ciclo_crud_completo(client, recurso):
    nombre, payload, _ = recurso
    base = f"/api/v1/{nombre}"

    creado = client.post(f"{base}/", json=payload)
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["nombre"] == payload["nombre"]
    assert cuerpo["cliente_id"] > 0
    # La credencial jamas viaja en las respuestas ordinarias.
    assert "contrasena" not in cuerpo
    assert "contrasena_cifrada" not in cuerpo
    assert "clave_natural" not in cuerpo

    registro_id = cuerpo["id"]

    listado = client.get(f"{base}/").json()
    assert listado["total"] == 1
    assert listado["items"][0]["id"] == registro_id

    assert client.get(f"{base}/{registro_id}").status_code == 200

    actualizado = client.patch(f"{base}/{registro_id}", json={"nombre": "Nombre Corregido"})
    assert actualizado.status_code == 200
    assert actualizado.json()["nombre"] == "Nombre Corregido"

    assert client.delete(f"{base}/{registro_id}").status_code == 204
    assert client.get(f"{base}/{registro_id}").status_code == 404


def test_busqueda_por_nombre_es_insensible_a_mayusculas(client, recurso):
    nombre, payload, _ = recurso
    base = f"/api/v1/{nombre}"
    client.post(f"{base}/", json=payload)

    fragmento = payload["nombre"].split()[0].lower()
    assert client.get(f"{base}/?buscar={fragmento}").json()["total"] == 1
    assert client.get(f"{base}/?buscar=inexistente").json()["total"] == 0


def test_borrado_es_logico_y_reversible(client, recurso):
    nombre, payload, _ = recurso
    base = f"/api/v1/{nombre}"
    registro_id = client.post(f"{base}/", json=payload).json()["id"]

    client.delete(f"{base}/{registro_id}")

    # Fuera de los listados ordinarios, pero conservado.
    assert client.get(f"{base}/").json()["total"] == 0
    ocultos = client.get(f"{base}/?incluir_eliminados=true").json()
    assert ocultos["total"] == 1
    assert ocultos["items"][0]["eliminado_en"] is not None

    restaurado = client.post(f"{base}/{registro_id}/restaurar")
    assert restaurado.status_code == 200
    assert restaurado.json()["eliminado_en"] is None
    assert client.get(f"{base}/").json()["total"] == 1


def test_restaurar_un_registro_activo_devuelve_404(client, recurso):
    nombre, payload, _ = recurso
    base = f"/api/v1/{nombre}"
    registro_id = client.post(f"{base}/", json=payload).json()["id"]

    assert client.post(f"{base}/{registro_id}/restaurar").status_code == 404


def test_operaciones_sobre_id_inexistente_devuelven_404(client, recurso):
    nombre, _, _ = recurso
    base = f"/api/v1/{nombre}"

    assert client.get(f"{base}/9999").status_code == 404
    assert client.patch(f"{base}/9999", json={"nombre": "X"}).status_code == 404
    assert client.delete(f"{base}/9999").status_code == 404


def test_alta_rechaza_nombre_vacio(client, recurso):
    nombre, payload, _ = recurso
    payload["nombre"] = ""
    assert client.post(f"/api/v1/{nombre}/", json=payload).status_code == 422


def test_ciclo_de_la_credencial_cifrada(client, recurso):
    nombre, payload, tiene_credencial = recurso
    base = f"/api/v1/{nombre}"

    if not tiene_credencial:
        # Pasaportes no maneja credenciales: el endpoint no debe existir.
        registro_id = client.post(f"{base}/", json=payload).json()["id"]
        assert client.get(f"{base}/{registro_id}/password").status_code == 404
        return

    registro_id = client.post(f"{base}/", json=payload).json()["id"]

    descifrada = client.get(f"{base}/{registro_id}/password")
    assert descifrada.status_code == 200
    assert descifrada.json()["contrasena"] == payload["contrasena"]

    client.patch(f"{base}/{registro_id}", json={"contrasena": "NuevaClave987"})
    assert client.get(f"{base}/{registro_id}/password").json()["contrasena"] == "NuevaClave987"


def test_patch_parcial_no_borra_los_campos_omitidos(client):
    """
    Un PATCH que omite un campo debe dejarlo intacto.

    Es la diferencia entre "no envie este campo" y "envie este campo como null",
    que son intenciones distintas y no deben confundirse.
    """
    creado = client.post(
        "/api/v1/master-tramex/",
        json={
            "nombre": "Jorge Monroy",
            "telefono": "4471148272",
            "tramite": "VISA B1/B2",
            "contrasena": "Secreta123",
        },
    ).json()

    actualizado = client.patch(
        f"/api/v1/master-tramex/{creado['id']}", json={"cita": "2026-09-01"}
    ).json()

    assert actualizado["cita"] == "2026-09-01"
    assert actualizado["telefono"] == "4471148272"
    assert actualizado["tramite"] == "VISA B1/B2"
    # La credencial tampoco debe perderse al no mencionarla.
    contrasena = client.get(f"/api/v1/master-tramex/{creado['id']}/password").json()
    assert contrasena["contrasena"] == "Secreta123"


def test_patch_con_null_explicito_si_borra_el_campo(client):
    creado = client.post(
        "/api/v1/master-tramex/", json={"nombre": "Jorge Monroy", "telefono": "4471148272"}
    ).json()

    actualizado = client.patch(
        f"/api/v1/master-tramex/{creado['id']}", json={"telefono": None}
    ).json()

    assert actualizado["telefono"] is None


def test_pasaporte_conserva_la_fecha_en_texto_libre(client):
    """
    El Excel original trae celdas de fecha con texto como "MARZO".

    El pipeline las preserva en `fecha_cita_original` en vez de descartarlas, y
    la API debe respetar esa distincion.
    """
    creado = client.post(
        "/api/v1/pasaportes/",
        json={"nombre": "Lucia", "lugar_cita": "GDL", "fecha_cita_original": "MARZO"},
    ).json()

    assert creado["fecha_cita"] is None
    assert creado["fecha_cita_original"] == "MARZO"


def test_paginacion_reporta_el_total_real(client):
    for indice in range(15):
        client.post("/api/v1/canada/", json={"nombre": f"Cliente {indice:02d}"})

    pagina = client.get("/api/v1/canada/?skip=10&limit=10").json()
    assert pagina["total"] == 15
    assert len(pagina["items"]) == 5
    assert pagina["skip"] == 10


def test_limite_de_pagina_esta_acotado(client):
    """Un `limit` desmedido debe rechazarse, no volcar la tabla entera."""
    assert client.get("/api/v1/canada/?limit=100000").status_code == 422


class TestOrdenDeListado:
    """
    El tablero de la pantalla inicial pregunta «qué ha pasado hoy».

    Por omisión el listado ordena por identificador, que es estable y sirve
    para paginar un catálogo; para el tablero hace falta lo último tocado.
    """

    def test_por_omision_ordena_por_identificador(self, client):
        for nombre in ("Tercero", "Primero", "Segundo"):
            client.post("/api/v1/canada/", json={"nombre": nombre})

        items = client.get("/api/v1/canada/").json()["items"]
        assert [r["id"] for r in items] == sorted(r["id"] for r in items)

    def test_orden_reciente_devuelve_primero_lo_ultimo_tocado(self, client, session):
        from datetime import datetime, timedelta

        from app.models import Canada

        antiguo = client.post("/api/v1/canada/", json={"nombre": "Antiguo"}).json()
        nuevo = client.post("/api/v1/canada/", json={"nombre": "Nuevo"}).json()

        # La marca de tiempo se fija a mano: CURRENT_TIMESTAMP tiene resolución
        # de un segundo, así que dos altas seguidas comparten instante y la
        # prueba mediría el desempate por id, no el orden que se quiere probar.
        ahora = datetime.now(UTC)
        session.get(Canada, nuevo["id"]).actualizado_en = ahora - timedelta(hours=2)
        session.get(Canada, antiguo["id"]).actualizado_en = ahora
        session.commit()

        items = client.get("/api/v1/canada/?orden=reciente").json()["items"]
        assert [r["nombre"] for r in items] == ["Antiguo", "Nuevo"]

    def test_un_orden_desconocido_se_rechaza(self, client):
        assert client.get("/api/v1/canada/?orden=inventado").status_code == 422
