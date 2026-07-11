# ===========================================================================
# Tests de Integración para los Routers de la API de Tramex
# ===========================================================================

def test_crud_master_tramex(client):
    # 1. POST (Creación y verificación de cifrado de contraseñas)
    payload = {
        "nombre": "Jorge Monroy",
        "id_solicitud": "SOL777",
        "telefono": "4471148272",
        "numero_pasaporte": "G33961340",
        "tramite": "VISA B1/B2",
        "cita": "Renovación",
        "correo_electronico": "jorge@test.com",
        "contrasena": "SuperPassword123"
    }
    response = client.post("/api/master-tramex/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Jorge Monroy"
    assert "id" in res_data
    # Asegurar que contrasena y contrasena_cifrada NO se devuelven en la respuesta
    assert "contrasena" not in res_data
    assert "contrasena_cifrada" not in res_data

    record_id = res_data["id"]

    # 2. GET List (Listar todos con paginación)
    response = client.get("/api/master-tramex/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["nombre"] == "Jorge Monroy"

    # 3. GET ID (Obtener registro individual)
    response = client.get(f"/api/master-tramex/{record_id}")
    assert response.status_code == 200
    assert response.json()["nombre"] == "Jorge Monroy"

    # 4. GET buscar (Buscar por nombre con filtro ILIKE)
    response = client.get("/api/master-tramex/?buscar=jorge")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/api/master-tramex/?buscar=maria")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 5. PATCH (Actualización parcial de campos)
    patch_data = {"nombre": "Jorge Ulices Monroy", "contrasena": "NuevoPassword987"}
    response = client.patch(f"/api/master-tramex/{record_id}", json=patch_data)
    assert response.status_code == 200
    assert response.json()["nombre"] == "Jorge Ulices Monroy"
    assert "contrasena" not in response.json()

    # 6. DELETE (Eliminación de registros)
    response = client.delete(f"/api/master-tramex/{record_id}")
    assert response.status_code == 204

    # 7. GET inexistente (Confirmar eliminación)
    response = client.get(f"/api/master-tramex/{record_id}")
    assert response.status_code == 404


def test_crud_global_entry(client):
    # 1. POST
    payload = {
        "nombre": "Ana",
        "apellido": "Lopez",
        "correo_electronico": "ana@test.com",
        "numero_pasaporte": "PAS987",
        "contrasena": "globalSecret"
    }
    response = client.post("/api/global-entry/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Ana"
    assert "contrasena" not in res_data
    assert "contrasena_cifrada" not in res_data

    record_id = res_data["id"]

    # 2. GET List
    response = client.get("/api/global-entry/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 3. PATCH
    response = client.patch(f"/api/global-entry/{record_id}", json={"apellido": "Lopez Diaz"})
    assert response.status_code == 200
    assert response.json()["apellido"] == "Lopez Diaz"

    # 4. DELETE
    response = client.delete(f"/api/global-entry/{record_id}")
    assert response.status_code == 204


def test_crud_pasaportes(client):
    # 1. POST
    payload = {
        "nombre": "Carlos",
        "apellido": "Gomez",
        "telefono": "5551234567",
        "lugar_cita": "CDMX",
        "fecha_cita": "2026-08-15"
    }
    response = client.post("/api/pasaportes/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Carlos"
    assert res_data["fecha_cita"] == "2026-08-15"

    record_id = res_data["id"]

    # 2. GET List
    response = client.get("/api/pasaportes/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 3. PATCH
    response = client.patch(f"/api/pasaportes/{record_id}", json={"fecha_cita": "2026-09-01"})
    assert response.status_code == 200
    assert response.json()["fecha_cita"] == "2026-09-01"

    # 4. DELETE
    response = client.delete(f"/api/pasaportes/{record_id}")
    assert response.status_code == 204


def test_crud_canada(client):
    # 1. POST
    payload = {
        "nombre": "Maria",
        "cuenta_ircc": "IRCC444",
        "telefono": "9998887776",
        "numero_pasaporte": "CAN1122",
        "contrasena": "canadaPass"
    }
    response = client.post("/api/canada/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Maria"
    assert "contrasena" not in res_data

    record_id = res_data["id"]

    # 2. GET List
    response = client.get("/api/canada/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 3. PATCH
    response = client.patch(f"/api/canada/{record_id}", json={"cuenta_ircc": "IRCC555"})
    assert response.status_code == 200
    assert response.json()["cuenta_ircc"] == "IRCC555"

    # 4. DELETE
    response = client.delete(f"/api/canada/{record_id}")
    assert response.status_code == 204
