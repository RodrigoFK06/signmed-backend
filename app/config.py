from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "app" / "models"

# Dataset and model paths
DATASET_PATH = DATA_DIR / "dataset_medico.csv"
LSTM_MODEL_PATH = MODELS_DIR / "lstm_model.h5"
CNN_LSTM_MODEL_PATH = MODELS_DIR / "cnn_lstm_model.h5"
ENCODER_PATH = MODELS_DIR / "label_encoder.pkl"

# Training parameters
EPOCHS = 25
BATCH_SIZE = 8
DATA_PATH = str(DATASET_PATH)  # For backward compatibility
TEST_SIZE = 0.2
RANDOM_STATE = 42

# Plot and metrics output paths
LSTM_PLOT_PATH = MODELS_DIR / "loss_plot_lstm.png"
CNN_LSTM_PLOT_PATH = MODELS_DIR / "loss_plot_cnn_lstm.png"
METRICS_JSON_PATH = MODELS_DIR / "metrics.json"
CONFUSION_MATRIX_PATH = MODELS_DIR / "confusion_matrix.png"
REPORT_PATH = MODELS_DIR / "classification_report.txt"
INFERENCE_LOG_PATH = MODELS_DIR / "inference_log.csv"
