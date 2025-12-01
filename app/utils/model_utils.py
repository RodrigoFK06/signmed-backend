# app/utils/model_utils.py
import os
import joblib
import matplotlib.pyplot as plt

def save_model(model, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    model.save(path)
    print(f"✅ Modelo guardado en: {path}")

def save_encoder(encoder, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(encoder, path)
    print(f"✅ Encoder guardado en: {path}")

def plot_metrics(history, save_path: str):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    acc = history.history.get("accuracy", [])
    val_acc = history.history.get("val_accuracy", [])
    loss = history.history.get("loss", [])
    val_loss = history.history.get("val_loss", [])

    plt.figure(figsize=(10,4))
    # Accuracy
    plt.subplot(1,2,1)
    plt.plot(acc, label="train")
    plt.plot(val_acc, label="val")
    plt.title("Accuracy")
    plt.legend()
    # Loss
    plt.subplot(1,2,2)
    plt.plot(loss, label="train")
    plt.plot(val_loss, label="val")
    plt.title("Loss")
    plt.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"📈 Gráficas de métricas guardadas en: {save_path}")
