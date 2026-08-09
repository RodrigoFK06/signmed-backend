import os
import json
import collections
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    Conv1D, MaxPooling1D, Dropout,
    BatchNormalization, LSTM, Dense, Input
)
from tensorflow.keras import regularizers
from tensorflow.keras.callbacks import EarlyStopping

from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix

import joblib  # <-- para guardar el encoder como pkl

# 🔧 Ajusta las importaciones al nuevo esquema
from app.utils.data_loader import load_dataset
from app.utils.model_utils import save_model, save_encoder, plot_metrics
from app.config import (
    ARTIFACTS_DIR,
    BATCH_SIZE,
    EPOCHS,
)

# --- CONFIGURACIÓN DEL NUEVO MODELO ---
MODELS_DIR   = ARTIFACTS_DIR
MODEL_PATH   = str(ARTIFACTS_DIR / "lstm_holistic.h5")
ENCODER_PATH = str(ARTIFACTS_DIR / "label_encoder.pkl")
CLASSES_PATH = str(ARTIFACTS_DIR / "classes.json")
PLOT_PATH    = str(ARTIFACTS_DIR / "lstm_holistic_plot.png")

MEAN_PATH = str(ARTIFACTS_DIR / "mean_holistic.npy")
STD_PATH  = str(ARTIFACTS_DIR / "std_holistic.npy")


# --- CONSTRUCCIÓN DEL MODELO ---
def build_model(num_classes: int) -> Sequential:
    model = Sequential([
        Input(shape=(35, 150)),  # 35 frames × 150 features
        Conv1D(64, 3, activation='relu'),
        BatchNormalization(),
        MaxPooling1D(),
        Dropout(0.4),

        Conv1D(128, 3, activation='relu'),
        BatchNormalization(),
        MaxPooling1D(),
        Dropout(0.4),

        LSTM(128, return_sequences=True),
        LSTM(64),

        Dense(64, activation='relu', kernel_regularizer=regularizers.l2(0.001)),
        Dropout(0.4),

        Dense(num_classes, activation='softmax')
    ])

    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    return model


# --- MATRIZ DE CONFUSIÓN ---
def plot_confusion(y_true, y_pred, encoder, save_path=None):
    if save_path is None:
        save_path = str(MODELS_DIR / "confusion_matrix_holistic.png")

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    labels = encoder.classes_
    matrix = confusion_matrix(y_true, y_pred)

    plt.figure(figsize=(10, 6))
    sns.heatmap(matrix, annot=True, fmt='d', cmap='Blues')
    plt.xlabel("Predicción")
    plt.ylabel("Real")
    plt.title("Matriz de Confusión (Holistic)")
    plt.xticks(ticks=np.arange(len(labels)) + 0.5, labels=labels, rotation=45, ha="right")
    plt.yticks(ticks=np.arange(len(labels)) + 0.5, labels=labels, rotation=0)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

    print(f"✅ Matriz de confusión guardada en: {save_path}")


# --- ENTRENAMIENTO PRINCIPAL ---
def main():
    print("📦 Cargando dataset Holistic (35x150)...")
    X_train, X_test, y_train, y_test, encoder = load_dataset()

    # --- Normalización ---
    # BUG CORREGIDO: la version anterior calculaba y guardaba mean/std pero
    # despues entrenaba con `X_train` en crudo, mientras que el servicio de
    # inferencia si estandarizaba la entrada. El modelo recibia en produccion una
    # distribucion que nunca habia visto (train/serve skew). Ahora la
    # estandarizacion se aplica aqui, de modo que entrenamiento e inferencia usan
    # exactamente la misma transformacion.
    mean = np.mean(X_train, axis=(0, 1))
    std = np.std(X_train, axis=(0, 1))
    std[std == 0] = 1.0  # evita dividir por cero en features constantes

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    np.save(MEAN_PATH, mean)
    np.save(STD_PATH, std)
    print(f"💾 mean/std guardados en:\n  {MEAN_PATH}\n  {STD_PATH}")

    # Las estadisticas se calculan solo sobre train y se aplican tambien a test,
    # para no filtrar informacion del conjunto de evaluacion.
    X_train = (X_train - mean) / std
    X_test = (X_test - mean) / std
    print("✅ Features estandarizadas con las estadisticas de entrenamiento.")
    print("   Recuerda desplegar con APPLY_FEATURE_NORMALIZATION=true.")

    print("\n🔍 Validación rápida del dataset:")
    print(f"➡️ Clases detectadas: {encoder.classes_}")
    print(f"➡️ X_train shape: {X_train.shape}, y_train: {y_train.shape}")
    print(f"➡️ X_test shape: {X_test.shape}, y_test: {y_test.shape}")

    # --- Distribución por clase ---
    train_dist = collections.Counter(y_train)
    print("\n📊 Distribución en y_train:")
    for label, count in train_dist.items():
        print(f"  - {encoder.inverse_transform([label])[0]}: {count} muestras")

    # --- Pesos por clase ---
    class_weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(y_train),
        y=y_train
    )
    class_weight_dict = dict(enumerate(class_weights))

    # --- Modelo ---
    num_classes = len(encoder.classes_)
    model = build_model(num_classes)
    model.summary()

    # Guardar resumen
    summary_path = str(MODELS_DIR / "lstm_holistic_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        model.summary(print_fn=lambda x: f.write(x + "\n"))
    print(f"📄 Resumen del modelo guardado en {summary_path}")

    # --- Entrenamiento ---
    early_stop = EarlyStopping(patience=5, restore_best_weights=True)
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        class_weight=class_weight_dict,
        callbacks=[early_stop],
        shuffle=True
    )

    # --- Guardar modelo y encoder ---
    save_model(model, MODEL_PATH)

    # Guarda encoder con joblib (y además vía tu helper por compatibilidad)
    joblib.dump(encoder, ENCODER_PATH)
    save_encoder(encoder, ENCODER_PATH)  # si tu helper añade logging/validaciones

    # Guarda también el orden de clases como json para auditoría
    with open(CLASSES_PATH, "w", encoding="utf-8") as f:
        json.dump(encoder.classes_.tolist(), f, ensure_ascii=False, indent=2)
    print(f"💾 Encoder: {ENCODER_PATH}\n💾 Clases:  {CLASSES_PATH}")

    plot_metrics(history, PLOT_PATH)

    print("\n📊 Evaluando modelo en test set:")
    test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
    print(f"✅ Accuracy en test: {test_acc:.4f} | Loss: {test_loss:.4f}")

    # --- Predicciones y reportes ---
    y_pred_probs = model.predict(X_test)
    y_pred = np.argmax(y_pred_probs, axis=1)
    
    # Usar labels para evitar error cuando alguna clase no aparece en test
    all_labels = list(range(len(encoder.classes_)))
    report = classification_report(
        y_test, 
        y_pred, 
        target_names=encoder.classes_,
        labels=all_labels,
        zero_division=0
    )
    print(report)

    with open(str(MODELS_DIR / "classification_report_holistic.txt"), "w", encoding="utf-8") as f:
        f.write(report)

    plot_confusion(y_test, y_pred, encoder)

    for i in range(min(5, len(X_test))):
        real = encoder.inverse_transform([y_test[i]])[0]
        pred = encoder.inverse_transform([np.argmax(y_pred_probs[i])])[0]
        print(f"▶️ Real: {real}")
        print(f"🤖 Pred: {pred}")
        print(f"📊 Probabilidades: {np.round(y_pred_probs[i], 3)}")
        print("-" * 30)

    # ✅ Coherencia final (defensivo): modelo ↔ encoder
    out_dim = model.output_shape[-1]
    assert out_dim == num_classes, (
        f"Modelo y encoder desalineados: out={out_dim} vs labels={num_classes}"
    )
    print("✅ Verificación de coherencia modelo↔encoder OK.")


if __name__ == "__main__":
    main()