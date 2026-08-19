"""
Tests for authentication, roles, and brute-force protection.

These replace the single test that existed before ("logging in with
admin/changeme returns a token"), which covered none of the controls that
now protect the API's most exposed endpoint.
"""

import pytest
from tests.conftest import CONTRASENA_DE_PRUEBA, CORREO_ADMIN, CORREO_OPERADOR

from app.security import COOKIE_SESION, hashear_contrasena, verificar_contrasena
from app.services import limitador


class TestHashing:
    def test_el_hash_no_contiene_la_contrasena(self):
        hash_generado = hashear_contrasena("mi-contrasena-secreta")
        assert "mi-contrasena-secreta" not in hash_generado
        assert hash_generado.startswith("$2b$")

    def test_dos_hashes_de_la_misma_contrasena_son_distintos(self):
        """Each hash carries its own salt, so they can't be grouped together."""
        assert hashear_contrasena("igual") != hashear_contrasena("igual")

    def test_verifica_correctamente(self):
        hash_generado = hashear_contrasena("correcta")
        assert verificar_contrasena("correcta", hash_generado) is True
        assert verificar_contrasena("incorrecta", hash_generado) is False

    def test_una_contrasena_de_mas_de_72_bytes_no_se_trunca(self):
        """
        bcrypt silently truncates at 72 bytes.

        Without the prior normalization, two very long passwords sharing
        the first 72 bytes would be interchangeable.
        """
        base = "x" * 80
        hash_generado = hashear_contrasena(base + "AAA")
        assert verificar_contrasena(base + "BBB", hash_generado) is False
        assert verificar_contrasena(base + "AAA", hash_generado) is True

    def test_un_hash_corrupto_no_revienta(self):
        assert verificar_contrasena("lo-que-sea", "no-es-un-hash") is False


class TestLogin:
    def test_login_correcto_devuelve_token_y_cookie(self, client_anonimo):
        respuesta = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        )
        assert respuesta.status_code == 200

        cuerpo = respuesta.json()
        assert cuerpo["token_type"] == "bearer"
        assert cuerpo["usuario"]["rol"] == "operador"
        # The password and its hash must never appear in the response.
        assert "contrasena" not in respuesta.text
        assert "hash" not in respuesta.text

        cookie = respuesta.cookies.get(COOKIE_SESION)
        assert cookie, "login must leave the session in a cookie"
        assert "httponly" in respuesta.headers["set-cookie"].lower()

    @pytest.mark.parametrize(
        ("correo", "contrasena"),
        [
            (CORREO_OPERADOR, "contrasena-equivocada"),
            ("no-existe@example.com", CONTRASENA_DE_PRUEBA),
        ],
    )
    def test_credenciales_invalidas_devuelven_401(self, client_anonimo, correo, contrasena):
        respuesta = client_anonimo.post(
            "/api/v1/auth/token", data={"username": correo, "password": contrasena}
        )
        assert respuesta.status_code == 401

    def test_el_mensaje_no_distingue_usuario_inexistente_de_contrasena_mala(self, client_anonimo):
        """Distinguishing them would allow enumerating which accounts exist."""
        inexistente = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": "fantasma@example.com", "password": "x" * 20},
        )
        mala = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": "x" * 20},
        )
        assert inexistente.json()["detail"] == mala.json()["detail"]

    def test_un_usuario_desactivado_no_puede_entrar(self, client_anonimo, session):
        from app.models import Usuario

        usuario = session.query(Usuario).filter_by(correo_electronico=CORREO_OPERADOR).one()
        usuario.activo = False
        session.commit()

        respuesta = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        )
        assert respuesta.status_code == 401


class TestSesion:
    def test_sin_sesion_los_recursos_devuelven_401(self, client_anonimo):
        for ruta in (
            "/api/v1/master-tramex/",
            "/api/v1/clientes/",
            "/api/v1/canada/1/password",
            "/api/v1/admin/auditoria",
        ):
            assert client_anonimo.get(ruta).status_code == 401, ruta

    def test_un_token_invalido_se_rechaza(self, client_anonimo):
        respuesta = client_anonimo.get(
            "/api/v1/master-tramex/", headers={"Authorization": "Bearer no-es-un-jwt"}
        )
        assert respuesta.status_code == 401

    def test_la_cabecera_bearer_tambien_funciona(self, client_anonimo):
        """Swagger and scripts don't use cookies."""
        token = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        ).json()["access_token"]
        client_anonimo.cookies.clear()

        respuesta = client_anonimo.get(
            "/api/v1/master-tramex/", headers={"Authorization": f"Bearer {token}"}
        )
        assert respuesta.status_code == 200

    def test_me_devuelve_al_usuario_de_la_sesion(self, client):
        cuerpo = client.get("/api/v1/auth/me").json()
        assert cuerpo["correo_electronico"] == CORREO_OPERADOR
        assert "contrasena_hash" not in cuerpo

    def test_logout_invalida_la_cookie(self, client):
        assert client.post("/api/v1/auth/logout").status_code == 204
        client.cookies.clear()
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_una_sesion_de_un_usuario_dado_de_baja_deja_de_valer(self, client, session):
        """
        A JWT is still cryptographically valid after someone is deactivated.

        Without checking the user's status on every request, that person
        would keep access until the token expired on its own.
        """
        from app.models import Usuario

        assert client.get("/api/v1/auth/me").status_code == 200

        usuario = session.query(Usuario).filter_by(correo_electronico=CORREO_OPERADOR).one()
        usuario.activo = False
        session.commit()

        assert client.get("/api/v1/auth/me").status_code == 401


class TestFuerzaBruta:
    def test_la_cuenta_se_bloquea_tras_varios_fallos(self, client_anonimo):
        from app.config import settings

        for _ in range(settings.intentos_maximos_login):
            respuesta = client_anonimo.post(
                "/api/v1/auth/token",
                data={"username": CORREO_OPERADOR, "password": "equivocada"},
            )
            assert respuesta.status_code == 401

        # The next attempt isn't even evaluated: the account is locked.
        bloqueado = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": "equivocada"},
        )
        assert bloqueado.status_code == 429
        assert "locked" in bloqueado.json()["detail"].lower()

    def test_el_bloqueo_resiste_aunque_la_contrasena_sea_la_correcta(self, client_anonimo):
        """Otherwise, just getting it right after exhausting attempts would work."""
        from app.config import settings

        for _ in range(settings.intentos_maximos_login):
            client_anonimo.post(
                "/api/v1/auth/token",
                data={"username": CORREO_OPERADOR, "password": "equivocada"},
            )

        respuesta = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        )
        assert respuesta.status_code == 429

    def test_bloquear_una_cuenta_no_bloquea_a_las_demas(self, client_anonimo):
        from app.config import settings

        for _ in range(settings.intentos_maximos_login + 1):
            client_anonimo.post(
                "/api/v1/auth/token",
                data={"username": CORREO_OPERADOR, "password": "equivocada"},
            )

        respuesta = client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_ADMIN, "password": CONTRASENA_DE_PRUEBA},
        )
        assert respuesta.status_code == 200

    def test_un_login_correcto_reinicia_el_contador(self, client_anonimo):
        for _ in range(2):
            client_anonimo.post(
                "/api/v1/auth/token",
                data={"username": CORREO_OPERADOR, "password": "equivocada"},
            )

        client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": CONTRASENA_DE_PRUEBA},
        )
        assert limitador.estado_de_cuenta(CORREO_OPERADOR).intentos == 0

    def test_la_ventana_no_se_prorroga_con_cada_intento(self):
        """
        A persistent attacker shouldn't be able to extend their own lockout.

        If every failure renewed the expiration, the window would never
        end and the legitimate account would stay locked indefinitely.
        """
        almacen = limitador.AlmacenEnMemoria()
        limitador.reiniciar_almacen(almacen)

        almacen.incrementar("clave", 60)
        primer_ttl = almacen.ttl("clave")
        almacen.incrementar("clave", 60)
        assert almacen.ttl("clave") <= primer_ttl


class TestCambioDeContrasena:
    def test_exige_la_contrasena_actual(self, client):
        respuesta = client.post(
            "/api/v1/auth/cambiar-contrasena",
            json={"contrasena_actual": "equivocada", "contrasena_nueva": "nueva-clave-larga-1"},
        )
        assert respuesta.status_code == 403

    def test_cambia_la_contrasena_y_la_nueva_sirve(self, client, client_anonimo):
        nueva = "una-contrasena-nueva-larga"
        assert (
            client.post(
                "/api/v1/auth/cambiar-contrasena",
                json={
                    "contrasena_actual": CONTRASENA_DE_PRUEBA,
                    "contrasena_nueva": nueva,
                },
            ).status_code
            == 204
        )

        client_anonimo.cookies.clear()
        assert (
            client_anonimo.post(
                "/api/v1/auth/token",
                data={"username": CORREO_OPERADOR, "password": nueva},
            ).status_code
            == 200
        )

    def test_rechaza_contrasenas_cortas(self, client):
        respuesta = client.post(
            "/api/v1/auth/cambiar-contrasena",
            json={"contrasena_actual": CONTRASENA_DE_PRUEBA, "contrasena_nueva": "corta"},
        )
        assert respuesta.status_code == 422

    def test_rechaza_repetir_la_misma_contrasena(self, client):
        respuesta = client.post(
            "/api/v1/auth/cambiar-contrasena",
            json={
                "contrasena_actual": CONTRASENA_DE_PRUEBA,
                "contrasena_nueva": CONTRASENA_DE_PRUEBA,
            },
        )
        assert respuesta.status_code == 422
