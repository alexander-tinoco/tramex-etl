"""
Tests for the audit log and role-based access control.

The system holds credentials for real clients' government accounts. Being
able to answer *who* looked up *which account* and *when* isn't an extra:
it's what makes it defensible that the API can decrypt them at all.
"""

from datetime import UTC

from tests.conftest import CONTRASENA_DE_PRUEBA, CORREO_ADMIN, CORREO_OPERADOR

from app.services.auditoria import Accion


def _crear_tramite(client, contrasena="CredencialDelCliente1"):
    return client.post(
        "/api/v1/master-tramex/",
        json={
            "nombre": "Jorge Monroy",
            "numero_pasaporte": "G33961340",
            "contrasena": contrasena,
        },
    ).json()


def _asientos(client_admin, **filtros):
    respuesta = client_admin.get("/api/v1/admin/auditoria", params=filtros)
    assert respuesta.status_code == 200
    return respuesta.json()["items"]


class TestRegistroDeEventos:
    def test_el_login_queda_asentado(self, client, client_admin):
        acciones = [a["accion"] for a in _asientos(client_admin)]
        assert Accion.LOGIN_EXITOSO in acciones

    def test_un_login_fallido_queda_asentado_con_severidad(self, client_anonimo, session):
        client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_OPERADOR, "password": "equivocada"},
        )
        client_anonimo.post(
            "/api/v1/auth/token",
            data={"username": CORREO_ADMIN, "password": CONTRASENA_DE_PRUEBA},
        )

        asientos = _asientos(client_anonimo, accion=Accion.LOGIN_FALLIDO)
        assert len(asientos) == 1
        assert asientos[0]["nivel"] == "ADVERTENCIA"
        assert asientos[0]["usuario_correo"] == CORREO_OPERADOR

    def test_las_operaciones_crud_quedan_asentadas(self, client, client_admin):
        registro = _crear_tramite(client)
        client.patch(f"/api/v1/master-tramex/{registro['id']}", json={"cita": "2026-09-01"})
        client.delete(f"/api/v1/master-tramex/{registro['id']}")
        client.post(f"/api/v1/master-tramex/{registro['id']}/restaurar")

        acciones = [a["accion"] for a in _asientos(client_admin)]
        for esperada in (
            Accion.REGISTRO_CREADO,
            Accion.REGISTRO_ACTUALIZADO,
            Accion.REGISTRO_ARCHIVADO,
            Accion.REGISTRO_RESTAURADO,
        ):
            assert esperada in acciones


class TestConsultaDeCredenciales:
    def test_descifrar_una_credencial_deja_rastro(self, client, client_admin):
        registro = _crear_tramite(client)

        respuesta = client.get(f"/api/v1/master-tramex/{registro['id']}/password")
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["contrasena"] == "CredencialDelCliente1"
        # The response indicates which audit entry the lookup was recorded in.
        assert cuerpo["auditoria_id"] > 0

        asiento = _asientos(client_admin, accion=Accion.CREDENCIAL_CONSULTADA)[0]
        assert asiento["id"] == cuerpo["auditoria_id"]
        assert asiento["usuario_correo"] == CORREO_OPERADOR
        assert asiento["recurso"] == "master_tramex"
        assert asiento["registro_id"] == registro["id"]
        assert asiento["cliente_id"] == registro["cliente_id"]
        assert asiento["nivel"] == "ADVERTENCIA"

    def test_el_asiento_nunca_contiene_la_credencial(self, client, client_admin):
        _crear_tramite(client, contrasena="ContrasenaQueNoDebeAparecer")
        registro_id = client.get("/api/v1/master-tramex/").json()["items"][0]["id"]
        client.get(f"/api/v1/master-tramex/{registro_id}/password")

        volcado = client_admin.get("/api/v1/admin/auditoria").text
        assert "ContrasenaQueNoDebeAparecer" not in volcado

    def test_un_criptograma_ilegible_devuelve_500_y_se_asienta(self, client, client_admin, session):
        """
        This used to silently return "no password".

        Confusing "this record has no credential" with "there's a
        ciphertext that won't open" hides a rotated key or a backup
        restored with a different one — exactly when client credentials
        are on the line.
        """
        from app.models import MasterTramex

        registro = _crear_tramite(client)
        fila = session.get(MasterTramex, registro["id"])
        fila.contrasena_cifrada = "gAAAAAB-esto-no-es-un-criptograma-valido"
        session.commit()

        respuesta = client.get(f"/api/v1/master-tramex/{registro['id']}/password")
        assert respuesta.status_code == 500
        assert "key" in respuesta.json()["detail"].lower()

        asiento = _asientos(client_admin, accion=Accion.CREDENCIAL_ILEGIBLE)[0]
        assert asiento["nivel"] == "ALERTA"

    def test_un_registro_sin_credencial_no_es_un_error(self, client):
        registro = client.post(
            "/api/v1/master-tramex/", json={"nombre": "Sin Credencial", "numero_pasaporte": "X9"}
        ).json()

        respuesta = client.get(f"/api/v1/master-tramex/{registro['id']}/password")
        assert respuesta.status_code == 200
        assert respuesta.json()["contrasena"] is None


class TestRoles:
    def test_una_operadora_no_puede_leer_la_bitacora(self, client):
        assert client.get("/api/v1/admin/auditoria").status_code == 403

    def test_una_operadora_no_puede_administrar_usuarios(self, client):
        assert client.get("/api/v1/admin/usuarios").status_code == 403
        assert (
            client.post(
                "/api/v1/admin/usuarios",
                json={
                    "correo_electronico": "nueva@example.com",
                    "nombre": "Nueva",
                    "contrasena": "una-contrasena-larga",
                },
            ).status_code
            == 403
        )

    def test_una_operadora_si_puede_operar_tramites(self, client):
        """Role-based access control shouldn't get in the way of daily work."""
        assert client.get("/api/v1/master-tramex/").status_code == 200
        assert _crear_tramite(client)["id"] > 0

    def test_un_admin_puede_administrar(self, client_admin):
        assert client_admin.get("/api/v1/admin/auditoria").status_code == 200
        assert client_admin.get("/api/v1/admin/usuarios").json()["total"] == 2


class TestGestionDeUsuarios:
    def test_alta_de_usuario(self, client_admin):
        respuesta = client_admin.post(
            "/api/v1/admin/usuarios",
            json={
                "correo_electronico": "Nueva.Operadora@Example.com",
                "nombre": "Nueva Operadora",
                "contrasena": "contrasena-suficientemente-larga",
            },
        )
        assert respuesta.status_code == 201
        # The email is normalized so two equivalent accounts can't exist.
        assert respuesta.json()["correo_electronico"] == "nueva.operadora@example.com"
        assert respuesta.json()["rol"] == "operador"
        assert "contrasena" not in respuesta.text

    def test_no_se_pueden_repetir_correos(self, client_admin):
        cuerpo = {
            "correo_electronico": CORREO_OPERADOR,
            "nombre": "Duplicada",
            "contrasena": "contrasena-suficientemente-larga",
        }
        assert client_admin.post("/api/v1/admin/usuarios", json=cuerpo).status_code == 409

    def test_rechaza_contrasenas_cortas(self, client_admin):
        respuesta = client_admin.post(
            "/api/v1/admin/usuarios",
            json={
                "correo_electronico": "corta@example.com",
                "nombre": "Corta",
                "contrasena": "corta",
            },
        )
        assert respuesta.status_code == 422

    def test_no_se_puede_dejar_el_sistema_sin_administradores(self, client_admin, session):
        """Recovering from that would require editing the database by hand."""
        from app.models import Rol, Usuario

        admin = session.query(Usuario).filter_by(correo_electronico=CORREO_ADMIN).one()
        assert session.query(Usuario).filter_by(rol=Rol.ADMIN).count() == 1

        respuesta = client_admin.patch(
            f"/api/v1/admin/usuarios/{admin.id}", json={"rol": "operador"}
        )
        assert respuesta.status_code == 409

    def test_un_admin_no_puede_darse_de_baja_a_si_mismo(self, client_admin, session):
        from app.models import Usuario

        admin = session.query(Usuario).filter_by(correo_electronico=CORREO_ADMIN).one()
        assert client_admin.delete(f"/api/v1/admin/usuarios/{admin.id}").status_code == 409


class TestRetencion:
    def test_la_purga_exige_confirmacion_explicita(self, client_admin):
        respuesta = client_admin.post("/api/v1/admin/retencion/ejecutar")
        assert respuesta.status_code == 400
        assert "irreversible" in respuesta.json()["detail"].lower()

    def test_no_purga_lo_archivado_recientemente(self, client, client_admin):
        registro = _crear_tramite(client)
        client.delete(f"/api/v1/master-tramex/{registro['id']}")

        resultado = client_admin.post(
            "/api/v1/admin/retencion/ejecutar", params={"confirmar": "true"}
        ).json()
        assert resultado["total_purgado"] == 0
        # Still archived, not destroyed.
        assert client.get("/api/v1/master-tramex/?incluir_eliminados=true").json()["total"] == 1

    def test_purga_lo_archivado_hace_mas_del_periodo_de_retencion(
        self, client, client_admin, session
    ):
        from datetime import datetime, timedelta

        from app.config import settings
        from app.models import MasterTramex

        registro = _crear_tramite(client)
        client.delete(f"/api/v1/master-tramex/{registro['id']}")

        fila = session.get(MasterTramex, registro["id"])
        fila.eliminado_en = datetime.now(UTC) - timedelta(days=settings.dias_retencion + 1)
        session.commit()

        resultado = client_admin.post(
            "/api/v1/admin/retencion/ejecutar", params={"confirmar": "true"}
        ).json()
        assert resultado["purgados_por_tabla"]["master_tramex"] == 1
        assert client.get("/api/v1/master-tramex/?incluir_eliminados=true").json()["total"] == 0
