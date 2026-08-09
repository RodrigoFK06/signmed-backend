"""Tests de la logica de evaluacion y de la validacion de forma del predictor."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi import HTTPException

from app.core.settings import settings
from app.services.predictor import CORRECT, DOUBTFUL, INCORRECT, _validate_shape, evaluate


class TestEvaluate:
    def test_acierto_con_confianza_alta(self):
        assert evaluate("dolor", "dolor", 92.0, threshold=75.0) == (CORRECT, True)

    def test_fallo_con_confianza_alta(self):
        assert evaluate("dolor", "yo", 92.0, threshold=75.0) == (INCORRECT, False)

    def test_confianza_baja_nunca_es_incorrecto(self):
        """Poca confianza significa 'no lo se', no 'lo hiciste mal'."""
        assert evaluate("dolor", "yo", 40.0, threshold=75.0) == (DOUBTFUL, False)
        assert evaluate("dolor", "dolor", 40.0, threshold=75.0) == (DOUBTFUL, False)

    def test_sin_etiqueta_esperada_no_se_puede_juzgar(self):
        assert evaluate("dolor", None, 99.0, threshold=75.0) == (DOUBTFUL, False)

    def test_el_umbral_es_inclusivo(self):
        assert evaluate("dolor", "dolor", 75.0, threshold=75.0) == (CORRECT, True)

    def test_umbral_por_defecto_desde_configuracion(self):
        """
        El codigo anterior fijaba `threshold=50.0` con el comentario
        "TEMPORAL: para pruebas", de modo que se daba por buena cualquier
        prediccion por encima del 50 %.
        """
        assert settings.confidence_threshold == 75.0
        just_below = settings.confidence_threshold - 0.1
        assert evaluate("dolor", "dolor", just_below)[0] == DOUBTFUL


class TestValidateShape:
    def test_acepta_la_forma_esperada(self):
        sequence = np.zeros((settings.sequence_frames, settings.sequence_features), dtype=np.float32)
        assert _validate_shape(sequence).shape == sequence.shape

    def test_rechaza_el_formato_legacy_de_42_features(self):
        """
        Antes se rellenaba (35, 42) con ceros hasta (35, 150). Las 42 features
        eran landmarks de una mano y las 150 del modelo son pose y cara, asi que
        el relleno producia una entrada sin sentido y una prediccion arbitraria.
        """
        sequence = np.zeros((35, 42), dtype=np.float32)
        with pytest.raises(HTTPException) as exc:
            _validate_shape(sequence)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "BAD_SHAPE"

    @pytest.mark.parametrize("shape", [(34, 150), (36, 150), (35, 149), (35,), (35, 150, 1)])
    def test_rechaza_cualquier_otra_forma(self, shape):
        with pytest.raises(HTTPException) as exc:
            _validate_shape(np.zeros(shape, dtype=np.float32))
        assert exc.value.status_code == 422
