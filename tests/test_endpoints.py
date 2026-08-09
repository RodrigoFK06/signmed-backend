"""Tests de extremo a extremo de la API sobre una base de datos en memoria."""
from __future__ import annotations

import pytest


def test_health_check(app_client):
    response = app_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


class TestLabels:
    def test_devuelve_las_senas_disponibles(self, app_client):
        response = app_client.get("/labels")
        assert response.status_code == 200

        body = response.json()
        assert body["count"] == len(body["labels"])
        assert body["count"] > 0

    def test_las_etiquetas_son_cacheables(self, app_client):
        """
        La version anterior enviaba `no-store` y releia un CSV de 135 MB en cada
        peticion. El catalogo solo cambia al publicar un modelo, asi que debe
        poder cachearse.
        """
        response = app_client.get("/labels")
        assert "no-store" not in response.headers.get("Cache-Control", "")
        assert "max-age" in response.headers.get("Cache-Control", "")

    def test_detalle_incluye_dificultad(self, app_client):
        response = app_client.get("/labels/detailed")
        assert response.status_code == 200

        for label in response.json()["labels"]:
            assert label["difficulty"] in {"beginner", "intermediate", "advanced"}
            assert label["name"]


class TestAuthentication:
    @pytest.mark.parametrize(
        "path",
        ["/records", "/progress", "/stats/global_distribution", "/progress/level-progress"],
    )
    def test_los_endpoints_privados_exigen_sesion(self, app_client, path):
        assert app_client.get(path).status_code == 401

    def test_predict_exige_sesion(self, app_client):
        response = app_client.post("/predict", json={"sequence": [], "expected_label": "dolor"})
        assert response.status_code == 401

    def test_signup_rechaza_el_rol_admin(self, app_client, collections):
        """El registro no puede conceder privilegios de administrador."""
        response = app_client.post(
            "/auth/signup",
            json={
                "email": "atacante@example.com",
                "password": "contrasena1",
                "nickname": "atacante",
                "role": "ADMIN",
            },
        )
        assert response.status_code == 422

    def test_signup_de_paciente_queda_aprobado(self, app_client, collections):
        response = app_client.post(
            "/auth/signup",
            json={"email": "ana@example.com", "password": "contrasena1", "nickname": "ana"},
        )
        assert response.status_code == 201

        body = response.json()
        assert body["role"] == "PATIENT"
        assert body["status"] == "approved"

    def test_personal_de_salud_queda_pendiente(self, app_client, collections):
        response = app_client.post(
            "/auth/signup",
            json={
                "email": "doc@example.com",
                "password": "contrasena1",
                "nickname": "doc",
                "role": "HEALTH_WORKER",
                "document_url": "/uploads/documents/x.pdf",
            },
        )
        assert response.status_code == 201
        assert response.json()["status"] == "pending"

    def test_personal_de_salud_sin_documento_es_rechazado(self, app_client, collections):
        response = app_client.post(
            "/auth/signup",
            json={
                "email": "doc2@example.com",
                "password": "contrasena1",
                "nickname": "doc2",
                "role": "HEALTH_WORKER",
            },
        )
        assert response.status_code == 400

    def test_login_con_credenciales_invalidas(self, app_client, collections):
        response = app_client.post(
            "/auth/login",
            json={"email": "nadie@example.com", "password": "contrasena1"},
        )
        assert response.status_code == 401


class TestSessionScopedEndpoints:
    def test_progreso_vacio_para_un_usuario_nuevo(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/progress")
        assert response.status_code == 200
        assert response.json() == []

    def test_registros_exponen_el_total(self, authenticated_client):
        """
        `X-Total-Count` debe viajar en `expose_headers`; sin eso el navegador no
        puede leerla en peticiones cross-origin y la paginacion se rompe.
        """
        client, _ = authenticated_client
        response = client.get("/records")
        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "0"

    def test_progreso_por_nivel_cubre_los_tres_niveles(self, authenticated_client):
        client, _ = authenticated_client
        response = client.get("/progress/level-progress")
        assert response.status_code == 200

        body = response.json()
        assert set(body) == {"beginner", "intermediate", "advanced"}
        assert all(level["completed_signs"] == 0 for level in body.values())
        assert body["beginner"]["total_signs"] > 0

    def test_no_se_puede_registrar_progreso_de_una_sena_inexistente(self, authenticated_client):
        """
        El codigo anterior avisaba por consola y aceptaba el label igualmente
        ("TEMPORAL: Para debugging, aceptar cualquier label"), de modo que
        cualquiera podia inflar su progreso.
        """
        client, _ = authenticated_client
        response = client.post(
            "/progress/increment-level",
            json={"level": "beginner", "label_id": "sena_inventada"},
        )
        assert response.status_code == 400

    def test_no_se_puede_registrar_una_sena_en_el_nivel_equivocado(self, authenticated_client):
        client, _ = authenticated_client
        response = client.post(
            "/progress/increment-level",
            json={"level": "advanced", "label_id": "dolor"},
        )
        assert response.status_code == 400


class TestUploads:
    def test_rechaza_lo_que_no_sea_pdf(self, app_client):
        response = app_client.post(
            "/upload-document",
            files={"file": ("malicioso.exe", b"MZ\x90\x00", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_rechaza_un_pdf_falso(self, app_client):
        """La extension no basta: se comprueba la cabecera del fichero."""
        response = app_client.post(
            "/upload-document",
            files={"file": ("falso.pdf", b"<html>no soy un pdf</html>", "application/pdf")},
        )
        assert response.status_code == 400

    def test_acepta_un_pdf_valido(self, app_client):
        response = app_client.post(
            "/upload-document",
            files={"file": ("titulo.pdf", b"%PDF-1.7\n%fake content", "application/pdf")},
        )
        assert response.status_code == 200

        body = response.json()
        assert body["url"].startswith("/uploads/documents/")
        # El nombre en disco nunca es el que envia el cliente.
        assert "titulo" not in body["url"]
