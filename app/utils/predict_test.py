import numpy as np
import csv
from app.services.model_loader import get_model, get_encoder
from app.config import DATASET_PATH

# Ruta del archivo CSV con una secuencia a probar
csv_path = str(DATASET_PATH)
# Nombre de la etiqueta a probar (puedes cambiarla)
etiqueta_objetivo = "tengo_dolor_de_garganta"

def cargar_una_secuencia(label_buscado):
    with open(csv_path, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[-1] == label_buscado:
                secuencia = np.array(row[:-1], dtype=np.float32).reshape((35, 42))
                return secuencia
    raise ValueError(f"No se encontró ninguna secuencia con la etiqueta '{label_buscado}'.")

def main():
    print(f"🔍 Buscando una secuencia con etiqueta: '{etiqueta_objetivo}'...")
    secuencia = cargar_una_secuencia(etiqueta_objetivo)

    print("📦 Secuencia cargada. Forma:", secuencia.shape)
    print("📈 Varianza:", np.var(secuencia))
    print("🎯 Primeros valores del primer frame:", secuencia[0][:5])

    # Obtener modelo y encoder de forma lazy
    model = get_model()
    encoder = get_encoder()

    # Predicción
    prediction = model.predict(np.array([secuencia]), verbose=0)
    y_pred = np.argmax(prediction)
    predicted_label = encoder.inverse_transform([y_pred])[0]
    confidence = float(prediction[0][y_pred]) * 100

    print("\n🧠 Resultado:")
    print(f"🔠 Etiqueta esperada: {etiqueta_objetivo}")
    print(f"🤖 Etiqueta predicha: {predicted_label}")
    print(f"📊 Confianza: {confidence:.2f}%")
    print(f"📚 Vector completo de predicción: {np.round(prediction[0], 4)}")

if __name__ == "__main__":
    main()
