def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Tramex API v1.0.0"}
