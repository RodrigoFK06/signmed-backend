import os
import joblib  # Evita errores de pickle
from app.config import CNN_LSTM_MODEL_PATH, ENCODER_PATH

# --- CARGA SEGURA DE TENSORFLOW ---
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    print("⚠️ TensorFlow no disponible. Modo de desarrollo activo.")
    TENSORFLOW_AVAILABLE = False

    class MockModel:
        def predict(self, data):
            import numpy as np
            return np.array([[0.8, 0.1, 0.1]])

    class MockEncoder:
        def __init__(self):
            self.classes_ = ["dolor_de_cabeza", "mareo", "fatiga"]

        def inverse_transform(self, encoded_labels):
            if hasattr(encoded_labels, "__iter__"):
                return [self.classes_[int(label) % len(self.classes_)] for label in encoded_labels]
            else:
                return self.classes_[int(encoded_labels) % len(self.classes_)]

    class MockTensorFlow:
        class keras:
            class models:
                @staticmethod
                def load_model(path):
                    print(f"🔄 Mock: Cargando modelo desde {path}")
                    return MockModel()

    tf = MockTensorFlow()

# --- RUTAS BASE DESDE CONFIGURACIÓN ---
MODEL_PATH = os.getenv("MODEL_PATH", str(CNN_LSTM_MODEL_PATH))
ENCODER_PATH_STR = os.getenv("ENCODER_PATH", str(ENCODER_PATH))

# --- VARIABLES GLOBALES (lazy loading) ---
_loaded_models = {}   # soporta múltiples modelos por ruta
_encoder = None


# --- FUNCIONES AUXILIARES ---
def _validate_path(path: str, file_type: str = "modelo"):
    """Valida que exista un archivo en la ruta especificada."""
    if not os.path.exists(path):
        raise OSError(f"❌ No se encontró el {file_type} en: {path}")
    return path


# --- CARGA DE MODELOS ---
def get_model(custom_path: str = None):
    """
    Carga el modelo especificado de forma lazy.
    Si no se indica custom_path, usa el modelo principal (CNN+LSTM).
    """
    global _loaded_models

    path = custom_path or MODEL_PATH

    # Reutilizar si ya está cargado
    if path in _loaded_models:
        return _loaded_models[path]

    if not TENSORFLOW_AVAILABLE:
        print("🔄 Mock: Creando modelo simulado (sin TensorFlow)")
        _loaded_models[path] = MockModel()
        return _loaded_models[path]

    # Validar existencia
    _validate_path(path, "modelo")
    print(f"🔄 Cargando modelo desde: {path}")

    try:
        model = tf.keras.models.load_model(path)
        print("✅ Modelo cargado exitosamente")
        _loaded_models[path] = model
        return model
    except Exception as e:
        raise RuntimeError(f"❌ Error al cargar modelo '{path}': {str(e)}")


# --- CARGA DEL ENCODER ---
def get_encoder():
    """Carga el encoder de forma lazy y reutilizable."""
    global _encoder

    if _encoder is not None:
        return _encoder

    if not TENSORFLOW_AVAILABLE:
        print("🔄 Mock: Creando encoder simulado")
        _encoder = MockEncoder()
        return _encoder

    _validate_path(ENCODER_PATH_STR, "encoder")
    print(f"🔄 Cargando encoder desde: {ENCODER_PATH_STR}")

    try:
        _encoder = joblib.load(ENCODER_PATH_STR)
        print("✅ Encoder cargado exitosamente")
        return _encoder
    except Exception as e:
        raise RuntimeError(f"❌ Error al cargar encoder '{ENCODER_PATH_STR}': {str(e)}")


# --- VALIDACIÓN INICIAL (solo rutas, no carga real) ---
if TENSORFLOW_AVAILABLE:
    try:
        _validate_path(MODEL_PATH)
        _validate_path(ENCODER_PATH_STR, "encoder")
        print("✅ Rutas de modelo y encoder validadas correctamente")
    except OSError as e:
        print(f"⚠️ Advertencia: {e}")
        print("Los modelos se cargarán cuando sean necesarios.")
else:
    print("ℹ️ Modo desarrollo: validación de rutas omitida (TensorFlow no disponible).")


# --- COMPATIBILIDAD RETROACTIVA ---
def model():
    """Alias legacy."""
    return get_model()

def encoder():
    """Alias legacy."""
    return get_encoder()

__all__ = ["get_model", "get_encoder", "model", "encoder"]
