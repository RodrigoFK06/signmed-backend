"""Tests de validacion de los modelos Pydantic."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import settings
from app.models.schema import PredictRequest, UserCreate

FRAMES = settings.sequence_frames
FEATURES = settings.sequence_features


def _valid_sequence():
    return [[0.0] * FEATURES for _ in range(FRAMES)]


class TestPredictRequest:
    def test_secuencia_valida(self):
        request = PredictRequest(sequence=_valid_sequence(), expected_label="dolor")
        assert len(request.sequence) == FRAMES

    def test_rechaza_numero_de_frames_incorrecto(self):
        with pytest.raises(ValidationError, match=f"exactamente {FRAMES} frames"):
            PredictRequest(sequence=[[0.0] * FEATURES] * (FRAMES - 1))

    def test_rechaza_frames_de_tamano_incorrecto(self):
        sequence = _valid_sequence()
        sequence[7] = [0.0] * 42
        with pytest.raises(ValidationError, match="el frame 8 tiene 42"):
            PredictRequest(sequence=sequence)

    def test_normaliza_la_etiqueta(self):
        request = PredictRequest(sequence=_valid_sequence(), expected_label="  DOLOR  ")
        assert request.expected_label == "dolor"

    def test_rechaza_etiquetas_desconocidas(self):
        with pytest.raises(ValidationError, match="no existe"):
            PredictRequest(sequence=_valid_sequence(), expected_label="etiqueta_inventada")

    def test_la_etiqueta_esperada_es_opcional(self):
        """El frontend permite practicar libremente, sin sena objetivo."""
        assert PredictRequest(sequence=_valid_sequence()).expected_label is None


class TestUserCreate:
    def test_alta_de_paciente(self):
        user = UserCreate(email="a@example.com", password="contrasena1", nickname="ana")
        assert user.role == "PATIENT"

    def test_no_se_puede_pedir_el_rol_admin(self):
        """
        Regresion de seguridad: `UserCreate.role` aceptaba todo `UserRole`, asi
        que cualquiera podia enviar {"role": "ADMIN"} a /auth/signup.
        """
        with pytest.raises(ValidationError):
            UserCreate(
                email="atacante@example.com",
                password="contrasena1",
                nickname="atacante",
                role="ADMIN",
            )

    def test_rechaza_contrasenas_cortas(self):
        with pytest.raises(ValidationError):
            UserCreate(email="a@example.com", password="corta", nickname="ana")

    def test_rechaza_email_invalido(self):
        with pytest.raises(ValidationError):
            UserCreate(email="no-es-un-email", password="contrasena1", nickname="ana")

    def test_rechaza_document_url_arbitraria(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="a@example.com",
                password="contrasena1",
                nickname="ana",
                role="HEALTH_WORKER",
                document_url="javascript:alert(1)",
            )
