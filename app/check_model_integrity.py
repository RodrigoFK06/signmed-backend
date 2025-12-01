import numpy as np
from tensorflow.keras.models import load_model
import joblib
from collections import Counter
from app.config import CNN_LSTM_MODEL_PATH, ENCODER_PATH

# Cargar modelo y encoder
model = load_model(CNN_LSTM_MODEL_PATH)
encoder = joblib.load(ENCODER_PATH)

# Generar 100 secuencias aleatorias (forma válida)
random_sequences = np.random.rand(100, 35, 42).astype(np.float32)

# Hacer predicciones
predictions = model.predict(random_sequences, verbose=0)
predicted_indices = np.argmax(predictions, axis=1)
predicted_labels = encoder.inverse_transform(predicted_indices)

# Contar cuántas veces se predice cada clase
counts = Counter(predicted_labels)

print("\n🧪 Diagnóstico de Predicciones sobre entradas aleatorias:")
print("----------------------------------------------------------")
for label, count in counts.items():
    print(f"{label}: {count} veces")

print("----------------------------------------------------------")
if len(counts) == 1:
    print("⚠️ El modelo predice siempre la MISMA clase. Probable sobreajuste o bug de entrenamiento.")
elif max(counts.values()) > 0.8 * sum(counts.values()):
    print("⚠️ El modelo está fuertemente sesgado hacia una clase.")
else:
    print("✅ El modelo distribuye bien las predicciones (no está sesgado con datos aleatorios).")
