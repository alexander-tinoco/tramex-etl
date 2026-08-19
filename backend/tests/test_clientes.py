"""
Tests for the model's root entity.

The value of the relational refactor is verified here: the same person
with tramites across several tables must resolve to a single client,
something the original Excel file didn't allow.
"""


def test_alta_de_cliente_es_idempotente(client):
    payload = {
        "nombre": "Jorge",
        "apellido": "Monroy",
        "numero_pasaporte": "G33961340",
        "correo_electronico": "jorge@example.com",
    }
    primero = client.post("/api/v1/clientes/", json=payload)
    assert primero.status_code == 201

    # Resubmitting the same client must not create a duplicate or violate the UNIQUE.
    segundo = client.post("/api/v1/clientes/", json=payload)
    assert segundo.status_code == 201
    assert segundo.json()["id"] == primero.json()["id"]

    assert client.get("/api/v1/clientes/").json()["total"] == 1


def test_la_clave_natural_ignora_acentos_y_espacios(client):
    base = client.post(
        "/api/v1/clientes/",
        json={"nombre": "José", "apellido": "Ramírez", "numero_pasaporte": "A1"},
    ).json()

    variante = client.post(
        "/api/v1/clientes/",
        json={"nombre": "  jose ", "apellido": "ramirez", "numero_pasaporte": "a1"},
    ).json()

    assert variante["id"] == base["id"]


def test_tramites_de_distintas_tablas_convergen_en_un_cliente(client):
    identidad = {"nombre": "Ana Lopez", "numero_pasaporte": "PAS987"}

    master = client.post("/api/v1/master-tramex/", json={**identidad, "tramite": "VISA B1/B2"})
    canada = client.post("/api/v1/canada/", json={**identidad, "cuenta_ircc": "IRCC444"})
    assert master.status_code == 201
    assert canada.status_code == 201

    # Both rows must hang off the same client.
    assert master.json()["cliente_id"] == canada.json()["cliente_id"]
    assert client.get("/api/v1/clientes/").json()["total"] == 1

    detalle = client.get(f"/api/v1/clientes/{master.json()['cliente_id']}").json()
    assert detalle["tramites"] == {
        "master_tramex": 1,
        "global_entry": 0,
        "pasaportes": 0,
        "canada": 1,
    }


def test_baja_de_cliente_arrastra_sus_tramites(client):
    creado = client.post(
        "/api/v1/master-tramex/", json={"nombre": "Carlos Gomez", "numero_pasaporte": "X1"}
    ).json()

    assert client.delete(f"/api/v1/clientes/{creado['cliente_id']}").status_code == 204

    assert client.get("/api/v1/clientes/").json()["total"] == 0
    assert client.get("/api/v1/master-tramex/").json()["total"] == 0
    # But the data still exists for traceability.
    assert client.get("/api/v1/master-tramex/?incluir_eliminados=true").json()["total"] == 1


def test_cliente_inexistente_devuelve_404(client):
    assert client.get("/api/v1/clientes/9999").status_code == 404
    assert client.delete("/api/v1/clientes/9999").status_code == 404
