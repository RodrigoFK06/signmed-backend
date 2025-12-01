import os
import tensorflow as tf
import numpy as np
from app.config import MODELS_DIR

MODEL_PATH = str(MODELS_DIR / "lstm_gestos_model.h5")

model = tf.keras.models.load_model(MODEL_PATH)

sample_data = np.random.rand(1, 35, 42)
prediction = model.predict(sample_data)

print("✅ Modelo cargado y predicción generada exitosamente.")
print("🔮 Output:", prediction)
