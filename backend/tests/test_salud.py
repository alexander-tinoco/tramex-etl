"""Health probes."""


def test_raiz_identifica_el_servicio(client):
    respuesta = client.get("/")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["message"].startswith("Tramex API v")


def test_health_verifica_la_base_de_datos(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["database"] == "connected"
