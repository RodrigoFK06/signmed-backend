import joblib
import os
from app.config import ENCODER_PATH

# Use centralized config for encoder path
encoder_path = str(ENCODER_PATH)

try:
    encoder = joblib.load(encoder_path)
    print("✅ Encoder cargado exitosamente.")
    print(f"Clases: {encoder.classes_}")
except Exception as e:
    print("❌ Error al cargar el encoder:")
    print(e)
