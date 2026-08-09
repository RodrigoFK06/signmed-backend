"""
Servicio de inferencia.

Tres decisiones que corrigen fallos del disenio anterior:

1. **Carga perezosa.** El modelo se cargaba al importar el modulo, asi que
   importar cualquier endpoint (o recolectar los tests) arrastraba TensorFlow y
   fallaba si el `.h5` no estaba. Ahora se carga una sola vez, bajo lock, en el
   arranque o en la primera prediccion.

2. **Sin bloquear el event loop.** `model.predict()` es sincrono y tarda decenas
   de milisegundos. Llamarlo dentro de un `async def` congelaba el servidor
   entero para todas las peticiones concurrentes. Ahora corre en el threadpool.

3. **Sin train/serve skew.** `train_cnn_lstm_model.py` calculaba y guardaba
   `mean/std` pero entrenaba con las features en crudo; en inferencia si se
   estandarizaba. El modelo recibia una distribucion que nunca vio. Por defecto
   se sirve igual que se entreno (ver `Settings.apply_feature_normalization` y
   `docs/MODEL_NOTES.md`).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool

from app.core.settings import settings
from app.models.schema import PredictRequest

logger = logging.getLogger(__name__)

CORRECT = "CORRECTO"
DOUBTFUL = "DUDOSO"
INCORRECT = "INCORRECTO"

_model: Any = None
_encoder: Any = None
_classes: np.ndarray = np.array([], dtype=object)
_mean: Optional[np.ndarray] = None
_std: Optional[np.ndarray] = None
_load_lock = asyncio.Lock()


class ModelUnavailableError(RuntimeError):
    """El modelo no pudo cargarse; la API debe responder 503, no 500."""


def _load_keras_model(model_path: Path):
    """
    Carga el `.h5` reconstruyendo la configuracion si trae parametros que Keras 3
    ya no acepta (`time_major` en LSTM, listas de un elemento en algunos campos).
    """
    import tensorflow as tf

    logger.info("Cargando modelo desde %s", model_path)
    try:
        return tf.keras.models.load_model(str(model_path))
    except (ValueError, TypeError) as exc:
        if "time_major" not in str(exc):
            raise

    logger.warning("Modelo con parametros deprecados; reconstruyendo capa a capa.")
    import json

    import h5py
    from keras import layers, models

    with h5py.File(model_path, "r") as handle:
        raw_config = handle.attrs.get("model_config")
        if not raw_config:
            raise ModelUnavailableError(f"{model_path} no contiene 'model_config'.")
        config = json.loads(raw_config.decode("utf-8") if isinstance(raw_config, bytes) else raw_config)

    unsupported = {"time_major", "batch_input_shape", "dtype", "module", "registered_name"}
    model = models.Sequential()

    for layer_config in config.get("config", {}).get("layers", []):
        class_name = layer_config.get("class_name")
        if class_name == "InputLayer":
            continue

        layer_class = getattr(layers, class_name, None)
        if layer_class is None:
            raise ModelUnavailableError(f"Capa desconocida en el modelo: {class_name}")

        params = {}
        for key, value in layer_config.get("config", {}).items():
            if key in unsupported:
                continue
            # Keras 2 serializaba algunos escalares como listas de un elemento.
            if isinstance(value, list) and len(value) == 1:
                value = value[0]
            if value is None:
                continue
            params[key] = value
        if class_name == "BatchNormalization":
            params.setdefault("axis", -1)

        model.add(layer_class(**params))

    model.load_weights(str(model_path))
    logger.info("Modelo reconstruido correctamente.")
    return model


def _load_artifacts() -> None:
    """Carga modelo, encoder y estadisticas. Idempotente."""
    global _model, _encoder, _classes, _mean, _std

    if _model is not None:
        return

    import joblib

    if not settings.model_path.exists():
        raise ModelUnavailableError(f"No se encontro el modelo en {settings.model_path}")
    if not settings.encoder_path.exists():
        raise ModelUnavailableError(f"No se encontro el encoder en {settings.encoder_path}")

    model = _load_keras_model(settings.model_path)
    encoder = joblib.load(str(settings.encoder_path))
    classes = np.array(getattr(encoder, "classes_", []), dtype=object)

    output_dim = model.output_shape[-1]
    if output_dim != len(classes):
        raise ModelUnavailableError(
            f"Modelo y encoder desalineados: salida={output_dim} vs clases={len(classes)}. "
            "Reexporta label_encoder.pkl y classes.json junto con el modelo."
        )

    mean = std = None
    if settings.apply_feature_normalization:
        mean_path = settings.artifacts_dir / "mean_holistic.npy"
        std_path = settings.artifacts_dir / "std_holistic.npy"
        if mean_path.exists() and std_path.exists():
            mean = np.load(str(mean_path))
            std = np.load(str(std_path))
            std = np.where(std == 0, 1.0, std)
        else:
            logger.warning(
                "apply_feature_normalization=True pero faltan mean/std en %s; se sirve sin normalizar.",
                settings.artifacts_dir,
            )

    _model, _encoder, _classes, _mean, _std = model, encoder, classes, mean, std
    logger.info("Modelo listo con %d clases: %s", len(classes), list(classes))


async def ensure_model_loaded() -> None:
    """Carga los artefactos si aun no lo estan, sin bloquear el event loop."""
    if _model is not None:
        return
    async with _load_lock:
        if _model is not None:
            return
        await run_in_threadpool(_load_artifacts)


def get_current_labels() -> list[str]:
    """Clases del modelo cargado, en el orden del encoder."""
    return _classes.tolist()


def _apply_normalization(sequence: np.ndarray) -> np.ndarray:
    if _mean is None or _std is None:
        return sequence
    return (sequence - _mean) / _std


def _validate_shape(sequence: np.ndarray) -> np.ndarray:
    """
    Exige exactamente (frames, features).

    El codigo anterior aceptaba (35, 42) y rellenaba con ceros hasta 150. Esa
    conversion no es valida: las 42 features del navegador eran landmarks de una
    mano, mientras que las 150 del entrenamiento son pose + cara. Rellenar con
    ceros producia una entrada sin significado y el modelo respondia
    practicamente al azar. Es preferible un 422 explicito.
    """
    expected = (settings.sequence_frames, settings.sequence_features)
    if sequence.shape != expected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "BAD_SHAPE",
                "message": f"Se esperaba una secuencia {expected}, se recibio {tuple(sequence.shape)}.",
            },
        )
    return sequence


def evaluate(
    predicted: str,
    expected: Optional[str],
    confidence: float,
    threshold: Optional[float] = None,
) -> Tuple[str, bool]:
    """
    Traduce (prediccion, esperado, confianza) a un veredicto.

    `DUDOSO` significa "el modelo no esta seguro", no "fallaste": por eso una
    confianza baja nunca se reporta como INCORRECTO aunque la etiqueta no
    coincida.
    """
    limit = settings.confidence_threshold if threshold is None else threshold

    if not expected:
        return DOUBTFUL, False
    if confidence < limit:
        return DOUBTFUL, False
    if predicted == expected:
        return CORRECT, True
    return INCORRECT, False


def _infer(sequence: np.ndarray) -> np.ndarray:
    """Inferencia sincrona. Se invoca siempre desde el threadpool."""
    batch = np.expand_dims(sequence, axis=0)
    return _model.predict(batch, verbose=0)[0]


async def _persist(document: Dict[str, Any], is_correct: bool) -> None:
    """
    Guarda el intento. Un fallo de base de datos no debe tumbar la prediccion,
    pero si debe quedar registrado (antes se silenciaba con `except: pass`).
    """
    try:
        from app.db.mongodb import get_collections
    except Exception:
        logger.debug("Capa de persistencia no disponible; no se registra el intento.")
        return

    try:
        collections = get_collections()
        await collections.predictions.insert_one(document)
        await collections.prediction_stats.update_one(
            {"expected_label": document["expected_label"], "user_id": document["user_id"]},
            {
                "$inc": {
                    "total": 1,
                    "correct": 1 if is_correct else 0,
                    "doubtful": 1 if document["evaluation"] == DOUBTFUL else 0,
                    "incorrect": 1 if document["evaluation"] == INCORRECT else 0,
                    "confidence_sum": float(document["confidence"]),
                },
                "$set": {"last_attempt": document["timestamp"]},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("No se pudo registrar el intento de prediccion.")


async def predict_sequence(
    request: PredictRequest,
    auth_nickname: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Ejecuta la inferencia y registra el intento."""
    try:
        await ensure_model_loaded()
    except ModelUnavailableError as exc:
        logger.error("Modelo no disponible: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "MODEL_UNAVAILABLE", "message": "El modelo de inferencia no esta disponible."},
        ) from exc

    try:
        sequence = np.asarray(request.sequence, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "BAD_PAYLOAD", "message": "La secuencia no es convertible a float32."},
        ) from exc

    sequence = _apply_normalization(_validate_shape(sequence))

    probabilities = await run_in_threadpool(_infer, sequence)
    best_index = int(np.argmax(probabilities))

    if best_index >= len(_classes):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "ENCODER_OUT_OF_DATE",
                "message": "El encoder no contiene todas las clases del modelo.",
                "pred_index": best_index,
                "known_labels": _classes.tolist(),
            },
        )

    label = str(_classes[best_index])
    confidence = float(np.max(probabilities) * 100.0)
    expected = request.expected_label
    verdict, is_correct = evaluate(label, expected, confidence)
    nickname = auth_nickname or request.nickname or None

    await _persist(
        {
            "timestamp": datetime.now(tz=timezone.utc),
            "user_id": user_id,
            "nickname": nickname,
            "predicted_label": label,
            "expected_label": expected,
            "confidence": confidence,
            "evaluation": verdict,
            "probabilities": [float(p) for p in probabilities],
        },
        is_correct,
    )

    return {
        "label": label,
        "confidence": confidence,
        "probabilities": [float(p) for p in probabilities],
        "evaluation": {"expected": expected, "final": verdict},
        "nickname": nickname,
    }
