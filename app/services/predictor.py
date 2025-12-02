import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import tensorflow as tf
from fastapi import HTTPException

from app.config import MODELS_DIR
from app.models.schema import PredictRequest

# (Opcional) Persistencia: intenta importar colecciones; si no existen, continúa sin romper
try:
    from app.db.mongodb import collection as records_collection  # historial detallado
    from app.db.mongodb import stats_collection                 # agregados por usuario/label
except Exception:  # pragma: no cover
    records_collection = None
    stats_collection = None

# --- Rutas de artefactos ---
MODEL_PATH   = Path(MODELS_DIR) / "lstm_holistic.h5"
ENCODER_PATH = Path(MODELS_DIR) / "label_encoder.pkl"
CLASSES_PATH = Path(MODELS_DIR) / "classes.json"
MEAN_PATH    = Path(MODELS_DIR) / "mean_holistic.npy"
STD_PATH     = Path(STD_PATH := MEAN_PATH.parent / "std_holistic.npy")  # mantener compat


def load_model_safe(model_path: Path):
    """Carga el modelo con manejo de parámetros deprecados de LSTM."""
    import h5py
    import json
    from keras import layers, models
    
    print(f"🔄 Cargando modelo desde {model_path}...")
    
    try:
        # Intenta carga normal primero
        return tf.keras.models.load_model(str(model_path))
    except (ValueError, TypeError) as e:
        if 'time_major' in str(e):
            print(f"⚠️ Modelo con parámetros deprecados detectado. Aplicando corrección automática...")
            
            # Leer configuración del modelo desde HDF5
            with h5py.File(model_path, 'r') as f:
                model_config = f.attrs.get('model_config')
                if not model_config:
                    raise ValueError("No se pudo obtener la configuración del modelo")
                
                # Decodificar configuración
                config_str = model_config.decode('utf-8') if isinstance(model_config, bytes) else model_config
                config = json.loads(config_str)
                
                # Función recursiva para eliminar time_major
                def remove_deprecated_params(obj):
                    if isinstance(obj, dict):
                        # Si es una capa LSTM, remover time_major
                        if obj.get('class_name') == 'LSTM' and 'config' in obj:
                            obj['config'].pop('time_major', None)
                        # Recursión en todos los valores
                        for value in obj.values():
                            remove_deprecated_params(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            remove_deprecated_params(item)
                
                # Limpiar configuración
                remove_deprecated_params(config)
                
                # Reconstruir modelo manualmente capa por capa
                print("✅ Configuración limpiada. Reconstruyendo modelo...")
                
                # Crear modelo Sequential
                model = models.Sequential()
                
                # Agregar capas desde la configuración
                layer_configs = config.get('config', {}).get('layers', [])
                for layer_config in layer_configs:
                    layer_class_name = layer_config.get('class_name')
                    layer_params = layer_config.get('config', {}).copy()
                    
                    # Saltar InputLayer (se crea automáticamente)
                    if layer_class_name == 'InputLayer':
                        continue
                    
                    # Normalizar parámetros que vienen como listas de un solo elemento
                    def normalize_param(value):
                        """Convierte listas de un elemento a valores únicos"""
                        if isinstance(value, list) and len(value) == 1:
                            return value[0]
                        elif isinstance(value, list) and len(value) == 0:
                            return None
                        return value
                    
                    # Aplicar normalización a todos los parámetros
                    for key in list(layer_params.keys()):
                        layer_params[key] = normalize_param(layer_params[key])
                    
                    # Parámetros específicos que necesitan valores por defecto si son None
                    if layer_params.get('axis') is None:
                        layer_params['axis'] = -1
                    
                    # Obtener la clase de capa correspondiente
                    layer_class = getattr(layers, layer_class_name, None)
                    if layer_class:
                        # Filtrar parámetros no soportados
                        unsupported = ['time_major', 'batch_input_shape', 'dtype', 'module', 'registered_name']
                        supported_params = {k: v for k, v in layer_params.items() 
                                          if k not in unsupported and v is not None}
                        try:
                            model.add(layer_class(**supported_params))
                        except Exception as layer_e:
                            print(f"⚠️ Error agregando capa {layer_class_name}: {layer_e}")
                            # Intenta con parámetros mínimos esenciales
                            if layer_class_name == 'LSTM':
                                model.add(layers.LSTM(units=supported_params.get('units', 128)))
                            elif layer_class_name in ['Conv1D', 'Dense']:
                                # Mantener solo los parámetros obligatorios
                                essential = {k: v for k, v in supported_params.items() 
                                           if k in ['units', 'filters', 'kernel_size']}
                                model.add(layer_class(**essential))
                            else:
                                raise
                
                # Cargar pesos del archivo original
                print("✅ Cargando pesos...")
                model.load_weights(str(model_path))
                print("✅ Modelo cargado exitosamente con compatibilidad TensorFlow 2.19")
                
                return model
        
        # Si es otro error, re-lanzarlo
        print(f"❌ Error al cargar modelo: {e}")
        raise


# --- Carga única al importar el módulo ---
model = load_model_safe(MODEL_PATH)
encoder = joblib.load(str(ENCODER_PATH))
classes = np.array(getattr(encoder, "classes_", []), dtype=object)  # np.array de strings

# (Opcional) comparar contra classes.json para auditar diferencias
if CLASSES_PATH.exists():
    try:
        with open(CLASSES_PATH, "r", encoding="utf-8") as f:
            classes_json = np.array(json.load(f), dtype=object)
        if len(classes) != len(classes_json) or np.any(classes != classes_json):
            print("⚠️ AVISO: classes.json y encoder.classes_ difieren. Se usará encoder.classes_.")
    except Exception:
        pass

# Normalizadores (si no existen, se predice sin normalizar)
mean = np.load(str(MEAN_PATH)) if MEAN_PATH.exists() else None
std  = np.load(str(STD_PATH)) if STD_PATH.exists() else None

# --- Sanity check modelo ↔ encoder ---
out_dim = model.output_shape[-1]
if out_dim != len(classes):
    raise RuntimeError(
        f"Modelo y encoder desalineados: model_out={out_dim} vs labels={len(classes)}. "
        f"Re-exporta label_encoder.pkl (y classes.json) con el dataset actual."
    )

def _normalize(x: np.ndarray) -> np.ndarray:
    """ Normaliza con mean/std guardados en training (shape (150,)). """
    if mean is None or std is None:
        return x
    s = std.copy()
    s[s == 0] = 1.0
    return (x - mean) / s

def _ensure_35x150(seq: np.ndarray) -> np.ndarray:
    """
    Acepta (35,150) o (35,42). Si es (35,42) -> pad a (35,150) con ceros en features.
    Lanza 422 si la forma es inválida.
    """
    if seq.ndim != 2:
        raise HTTPException(
            status_code=422,
            detail={"error": "BAD_SHAPE", "message": f"Esperado 2D (frames, features), recibido {seq.ndim}D"}
        )

    if seq.shape == (35, 150):
        return seq

    if seq.shape == (35, 42):
        # Pad a 150 features: [x1,y1, ..., x21,y21, 0,0,0...]
        pad_width = 150 - 42
        padded = np.pad(seq, ((0, 0), (0, pad_width)), mode="constant", constant_values=0.0)
        return padded

    # Cualquier otra forma es inválida
    raise HTTPException(
        status_code=422,
        detail={"error": "BAD_SHAPE", "message": f"Esperado (35,150) o (35,42), recibido {tuple(seq.shape)}"}
    )

def get_current_labels() -> list[str]:
    """ Devuelve las etiquetas actuales (orden del encoder). """
    return classes.tolist()

def _evaluate(predicted: str, expected: Optional[str], conf_pct: float, *, threshold: float = 75.0):
    """
    Regresa (evaluation_str, is_correct).
    Regla simple:
      - Si no hay expected -> 'DUDOSO'
      - Si predicted == expected:
          conf >= threshold -> 'CORRECTO'
          si no -> 'DUDOSO'
      - Si predicted != expected:
          conf >= threshold -> 'INCORRECTO'
          si no -> 'DUDOSO'
    """
    if not expected:
        return "DUDOSO", False

    if predicted == expected:
        return ("CORRECTO", True) if conf_pct >= threshold else ("DUDOSO", False)

    # No coincide
    return ("INCORRECTO", False) if conf_pct >= threshold else ("DUDOSO", False)

async def predict_sequence(req: PredictRequest, auth_nickname: Optional[str] = None, user_id: Optional[str] = None):
    """
    Recibe una secuencia (35x150) o (35x42), la adapta a (35x150),
    y devuelve:
      {
        "label": str,
        "confidence": float (0-100),
        "probabilities": number[] (0..1),
        "evaluation": {"expected": str | None, "final": "CORRECTO|DUDOSO|INCORRECTO"},
        "nickname": str | None
      }
    """
    # Convertir a np.array y asegurar tipo
    try:
        seq = np.asarray(req.sequence, dtype=np.float32)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={"error": "BAD_PAYLOAD", "message": "sequence no convertible a float32"}
        )

    # Adaptar forma a (35,150)
    seq = _ensure_35x150(seq)

    # Normalización idéntica a training (vector de 150)
    seq = _normalize(seq)

    # (1, 35, 150)
    x = np.expand_dims(seq, axis=0)
    probs = model.predict(x, verbose=0)[0]  # (num_classes,)
    idx = int(np.argmax(probs))

    try:
        label = encoder.inverse_transform([idx])[0]
    except Exception:
        # Captura p.ej. "y contains previously unseen labels"
        raise HTTPException(
            status_code=422,
            detail={
                "error": "ENCODER_OUT_OF_DATE",
                "message": "El encoder no contiene todas las clases del modelo.",
                "pred_index": idx,
                "known_labels": classes.tolist(),
            }
        )

    # Probabilidad máxima en porcentaje (0-100)
    conf_pct = float(np.max(probs) * 100.0)

    # Evaluación y usuario autenticado
    expected = getattr(req, "expected_label", None)
    # TEMPORAL: threshold=50.0 para pruebas (cualquier predicción >= 50% es CORRECTO)
    evaluation, is_correct = _evaluate(label, expected, conf_pct, threshold=50.0)

    nickname = auth_nickname or getattr(req, "nickname", None) or None  # priorizar JWT

    # Persistencia defensiva (si hay colecciones disponibles)
    if records_collection is not None:
        try:
            doc = {
                "timestamp": datetime.now(tz=timezone.utc),
                "user_id": user_id,  # ID del usuario autenticado
                "nickname": nickname,  # Mantener por compatibilidad
                "predicted_label": label,
                "expected_label": expected,
                "confidence": conf_pct,
                "evaluation": evaluation,
                "probabilities": probs.tolist(),
            }
            await records_collection.insert_one(doc)

            if stats_collection is not None:
                inc = {
                    "total": 1,
                    "correct": 1 if is_correct else 0,
                    "doubtful": 1 if evaluation == "DUDOSO" else 0,
                    "incorrect": 1 if evaluation == "INCORRECTO" else 0,
                    "confidence_sum": float(conf_pct),
                }
                # Usar user_id en lugar de nickname para las estadísticas
                await stats_collection.update_one(
                    {"expected_label": expected, "user_id": user_id},
                    {"$inc": inc, "$set": {"last_attempt": doc["timestamp"]}},
                    upsert=True,
                )
        except Exception as _:
            # No romper si DB falla
            pass

    return {
        "label": label,
        "confidence": conf_pct,
        "probabilities": probs.tolist(),  # en 0..1
        "evaluation": {"expected": expected, "final": evaluation},
        "nickname": nickname,
    }
