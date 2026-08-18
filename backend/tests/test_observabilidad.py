"""Pruebas de metricas y cabeceras de seguridad."""

from tests.conftest import CONTRASENA_DE_PRUEBA, CORREO_OPERADOR


class TestCabecerasDeSeguridad:
    def test_toda_respuesta_lleva_las_cabeceras(self, client_anonimo):
        cabeceras = client_anonimo.get("/").headers
        assert cabeceras["X-Content-Type-Options"] == "nosniff"
        assert cabeceras["X-Frame-Options"] == "DENY"
        assert cabeceras["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in cabeceras["Content-Security-Policy"]

    def test_tambien_en_las_respuestas_de_error(self, client_anonimo):
        """Una respuesta 401 tambien la interpreta el navegador."""
        cabeceras = client_anonimo.get("/api/v1/master-tramex/").headers
        assert cabeceras["X-Content-Type-Options"] == "nosniff"

    def test_hsts_solo_en_produccion(self, client_anonimo):
        """
        En desarrollo se trabaja sobre http.

        Enviar HSTS ahi dejaria el navegador forzando https contra un servidor
        que no lo habla, y el efecto persiste aunque se quite la cabecera.
        """
        assert "Strict-Transport-Security" not in client_anonimo.get("/").headers


class TestMetricas:
    def test_expone_el_formato_de_prometheus(self, client_anonimo):
        respuesta = client_anonimo.get("/metrics")
        assert respuesta.status_code == 200
        assert "text/plain" in respuesta.headers["content-type"]
        assert "tramex_peticiones_total" in respuesta.text

    def test_la_ruta_se_agrupa_por_plantilla(self, client):
        """
        Sin normalizar, cada id generaria su propia serie temporal.

        Es la forma habitual de tumbar un Prometheus por cardinalidad.
        """
        registro = client.post(
            "/api/v1/canada/", json={"nombre": "Metricas", "numero_pasaporte": "M1"}
        ).json()
        client.get(f"/api/v1/canada/{registro['id']}")

        cuerpo = client.get("/metrics").text
        assert 'ruta="/api/v1/canada/{registro_id}"' in cuerpo
        assert f'ruta="/api/v1/canada/{registro["id"]}"' not in cuerpo

    def test_cuenta_las_consultas_de_credenciales(self, client):
        registro = client.post(
            "/api/v1/canada/",
            json={"nombre": "Con Clave", "numero_pasaporte": "C1", "contrasena": "clave-1234"},
        ).json()
        client.get(f"/api/v1/canada/{registro['id']}/password")

        cuerpo = client.get("/metrics").text
        assert 'tramex_credenciales_consultadas_total{recurso="canada",resultado="ok"}' in cuerpo

    def test_cuenta_los_intentos_de_login(self, client_anonimo):
        client_anonimo.post(
            "/api/v1/auth/token", data={"username": CORREO_OPERADOR, "password": "mala"}
        )
        client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        )

        cuerpo = client_anonimo.get("/metrics").text
        assert 'tramex_intentos_login_total{resultado="fallido"}' in cuerpo
        assert 'tramex_intentos_login_total{resultado="exitoso"}' in cuerpo

    def test_las_metricas_no_revelan_datos_de_clientes(self, client):
        """Son agregados: no deben contener nombres ni identificadores."""
        client.post(
            "/api/v1/canada/",
            json={"nombre": "Nombre Confidencial", "contrasena": "clave-secreta-1234"},
        )
        cuerpo = client.get("/metrics").text
        assert "Nombre Confidencial" not in cuerpo
        assert "clave-secreta-1234" not in cuerpo


class TestDocumentacionInteractiva:
    """
    La politica cerrada de la API no debe romper Swagger.

    Swagger UI carga sus recursos desde un CDN; con `default-src 'none'` la
    pagina se renderiza en blanco y la documentacion interactiva deja de servir
    para nada, que es justo lo que paso al anadir las cabeceras.
    """

    def test_swagger_responde(self, client_anonimo):
        respuesta = client_anonimo.get("/docs")
        assert respuesta.status_code == 200
        assert "swagger" in respuesta.text.lower()

    def test_swagger_recibe_una_politica_que_permite_su_cdn(self, client_anonimo):
        politica = client_anonimo.get("/docs").headers["Content-Security-Policy"]
        assert "cdn.jsdelivr.net" in politica
        # Sigue siendo restrictiva: nada de incrustar la pagina en un marco.
        assert "frame-ancestors 'none'" in politica

    def test_el_resto_de_la_api_conserva_la_politica_cerrada(self, client_anonimo):
        politica = client_anonimo.get("/").headers["Content-Security-Policy"]
        assert politica.startswith("default-src 'none'")
        assert "cdn.jsdelivr.net" not in politica

    def test_el_esquema_openapi_se_genera(self, client_anonimo):
        esquema = client_anonimo.get("/openapi.json").json()
        assert esquema["info"]["title"] == "Tramex API"
        # Los cuatro recursos y la administracion estan documentados.
        rutas = esquema["paths"]
        assert "/api/v1/master-tramex/" in rutas
        assert "/api/v1/admin/auditoria" in rutas
