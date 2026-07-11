# ===========================================================================
# Tests de Integración – Tramex API
# ===========================================================================
# Los tests de routers usan el cliente de pruebas con auth y BD en memoria.
# La respuesta de listado ahora tiene forma PaginatedResponse:
#   { "total": int, "skip": int, "limit": int, "items": [...] }
# ===========================================================================

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Tramex API v1.0.0"}


def test_health_db(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_login_correcto(client):
    """Login con credenciales correctas (admin/changeme por defecto en tests)."""
    response = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "changeme"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_incorrecto(client):
    response = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


def test_endpoint_sin_token(client):
    """Sin el override de get_current_user (token real requerido), debería dar 401."""
    from app.security import get_current_user
    # Eliminar el override de auth para este test
    del client.app.dependency_overrides[get_current_user]
    response = client.get("/api/master-tramex/")
    assert response.status_code == 401
    # Restaurar el override para no afectar otros tests
    client.app.dependency_overrides[get_current_user] = lambda: "test_user"


# ---------------------------------------------------------------------------
# CRUD Master Tramex
# ---------------------------------------------------------------------------

def test_crud_master_tramex(client):
    # 1. POST – Creación con contraseña (verificar que no se devuelve en respuesta)
    payload = {
        "nombre": "Jorge Monroy",
        "id_solicitud": "SOL777",
        "telefono": "4471148272",
        "numero_pasaporte": "G33961340",
        "tramite": "VISA B1/B2",
        "cita": "Renovación",
        "correo_electronico": "jorge@test.com",
        "contrasena": "SuperPassword123",
    }
    response = client.post("/api/master-tramex/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Jorge Monroy"
    assert "id" in res_data
    assert "contrasena" not in res_data
    assert "contrasena_cifrada" not in res_data

    record_id = res_data["id"]

    # 2. GET List – respuesta paginada
    response = client.get("/api/master-tramex/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["nombre"] == "Jorge Monroy"

    # 3. GET por ID
    response = client.get(f"/api/master-tramex/{record_id}")
    assert response.status_code == 200
    assert response.json()["nombre"] == "Jorge Monroy"

    # 4. GET buscar – filtro ILIKE
    response = client.get("/api/master-tramex/?buscar=jorge")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get("/api/master-tramex/?buscar=maria")
    assert response.status_code == 200
    assert response.json()["total"] == 0

    # 5. GET password – descifrar contraseña
    response = client.get(f"/api/master-tramex/{record_id}/password")
    assert response.status_code == 200
    assert response.json()["contrasena"] == "SuperPassword123"

    # 6. PATCH – actualización parcial
    response = client.patch(
        f"/api/master-tramex/{record_id}",
        json={"nombre": "Jorge Ulices Monroy", "contrasena": "NuevoPassword987"},
    )
    assert response.status_code == 200
    assert response.json()["nombre"] == "Jorge Ulices Monroy"
    assert "contrasena" not in response.json()

    # Verificar que la nueva contraseña se descifra correctamente
    response = client.get(f"/api/master-tramex/{record_id}/password")
    assert response.json()["contrasena"] == "NuevoPassword987"

    # 7. DELETE
    response = client.delete(f"/api/master-tramex/{record_id}")
    assert response.status_code == 204

    # 8. GET inexistente – confirmar eliminación
    response = client.get(f"/api/master-tramex/{record_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# CRUD Global Entry
# ---------------------------------------------------------------------------

def test_crud_global_entry(client):
    payload = {
        "nombre": "Ana",
        "apellido": "Lopez",
        "correo_electronico": "ana@test.com",
        "numero_pasaporte": "PAS987",
        "contrasena": "globalSecret",
    }
    response = client.post("/api/global-entry/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Ana"
    assert "contrasena" not in res_data

    record_id = res_data["id"]

    response = client.get("/api/global-entry/")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get(f"/api/global-entry/{record_id}/password")
    assert response.json()["contrasena"] == "globalSecret"

    response = client.patch(f"/api/global-entry/{record_id}", json={"apellido": "Lopez Diaz"})
    assert response.status_code == 200
    assert response.json()["apellido"] == "Lopez Diaz"

    response = client.delete(f"/api/global-entry/{record_id}")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# CRUD Pasaportes
# ---------------------------------------------------------------------------

def test_crud_pasaportes(client):
    payload = {
        "nombre": "Carlos",
        "apellido": "Gomez",
        "telefono": "5551234567",
        "lugar_cita": "CDMX",
        "fecha_cita": "2026-08-15",
    }
    response = client.post("/api/pasaportes/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Carlos"
    assert res_data["fecha_cita"] == "2026-08-15"

    record_id = res_data["id"]

    response = client.get("/api/pasaportes/")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.patch(f"/api/pasaportes/{record_id}", json={"fecha_cita": "2026-09-01"})
    assert response.status_code == 200
    assert response.json()["fecha_cita"] == "2026-09-01"

    response = client.delete(f"/api/pasaportes/{record_id}")
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# CRUD Canadá
# ---------------------------------------------------------------------------

def test_crud_canada(client):
    payload = {
        "nombre": "Maria",
        "cuenta_ircc": "IRCC444",
        "telefono": "9998887776",
        "numero_pasaporte": "CAN1122",
        "contrasena": "canadaPass",
    }
    response = client.post("/api/canada/", json=payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["nombre"] == "Maria"
    assert "contrasena" not in res_data

    record_id = res_data["id"]

    response = client.get("/api/canada/")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get(f"/api/canada/{record_id}/password")
    assert response.json()["contrasena"] == "canadaPass"

    response = client.patch(f"/api/canada/{record_id}", json={"cuenta_ircc": "IRCC555"})
    assert response.status_code == 200
    assert response.json()["cuenta_ircc"] == "IRCC555"

    response = client.delete(f"/api/canada/{record_id}")
    assert response.status_code == 204
