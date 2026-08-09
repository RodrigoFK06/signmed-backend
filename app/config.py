"""
Rutas y parametros de los scripts de entrenamiento.

La configuracion del servicio vive en `app.core.settings`. Este modulo solo
expone lo que necesitan los scripts offline (entrenamiento, grabacion de
secuencias, analisis), que si pueden leer el dataset completo.
"""
from app.core.settings import settings

BASE_DIR = settings.artifacts_dir.parent
DATA_DIR = settings.data_dir
ARTIFACTS_DIR = settings.artifacts_dir

DATASET_PATH = settings.dataset_path

MODEL_PATH = settings.model_path
ENCODER_PATH = settings.encoder_path
CLASSES_PATH = settings.classes_path
MEAN_PATH = ARTIFACTS_DIR / "mean_holistic.npy"
STD_PATH = ARTIFACTS_DIR / "std_holistic.npy"

# Estructura de una secuencia: 35 frames x 150 features.
FRAMES = settings.sequence_frames
FEATURES_PER_FRAME = settings.sequence_features

# Hiperparametros de entrenamiento.
EPOCHS = 60
BATCH_SIZE = 32
TEST_SIZE = 0.2
RANDOM_STATE = 42
MIN_SAMPLES_PER_CLASS = 10

# Salidas de la evaluacion.
PLOT_PATH = ARTIFACTS_DIR / "lstm_holistic_plot.png"
METRICS_JSON_PATH = ARTIFACTS_DIR / "metrics.json"
CONFUSION_MATRIX_PATH = ARTIFACTS_DIR / "confusion_matrix_holistic.png"
REPORT_PATH = ARTIFACTS_DIR / "classification_report_holistic.txt"
