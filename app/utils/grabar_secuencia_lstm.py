"""
Grabador de secuencias para ampliar el dataset.

El vector de cada frame lo construye `app.utils.feature_extraction`, que
documenta y corrige el recorte que dejaba las manos fuera del dataset original.
"""
import cv2
import time
import os
import numpy as np
from app.utils.holistic_tracking import HolisticTracker
from app.utils.feature_extraction import FEATURES_PER_FRAME, build_frame_vector, has_hands
from app.config import DATASET_PATH

# --- CONFIGURACIÓN GENERAL ---
SEQUENCE_DURATION = 4.0
FPS = 10
FRAMES_TOTAL = int(SEQUENCE_DURATION * FPS)    # 40
FRAMES_TO_SKIP = 5                             # descartar primeros 5
FRAMES_TO_SAVE = FRAMES_TOTAL - FRAMES_TO_SKIP # 35
LANDMARKS_PER_FRAME = FEATURES_PER_FRAME       # 150
BOX_WIDTH = 560
BOX_HEIGHT = 480

tracker = HolisticTracker()
CSV_PATH = str(DATASET_PATH)

# --- FUNCIONES AUXILIARES ---
def _safe_makedirs_for_file(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def save_sequence(sequence, label, level, output_path=CSV_PATH):
    """Guarda la secuencia de frames en el CSV."""
    if len(sequence) != FRAMES_TO_SAVE:
        raise ValueError(f"La secuencia debe tener exactamente {FRAMES_TO_SAVE} frames.")
    for i, frame in enumerate(sequence):
        if len(frame) != LANDMARKS_PER_FRAME:
            raise ValueError(f"El frame {i} no tiene {LANDMARKS_PER_FRAME} valores.")

    row = []
    for frame in sequence:
        row.extend(frame)
    row.append(label)
    row.append(level)

    _safe_makedirs_for_file(output_path)
    from csv import writer
    with open(output_path, mode="a", newline="") as f:
        w = writer(f)
        w.writerow(row)

# --- PREGUNTAS INICIALES ---
print("🔠 Ingresa el nombre de la frase o secuencia (ej: tengo_fiebre_y_tos):")
etiqueta = input("Etiqueta: ").strip().lower().replace(" ", "_")

niveles_validos = {"1": "principiante", "2": "intermedio", "3": "avanzado"}
nivel = ""
while nivel not in niveles_validos:
    print("\n📈 Selecciona el nivel de dificultad:")
    print("  1 - Principiante")
    print("  2 - Intermedio")
    print("  3 - Avanzado")
    nivel = input("Nivel (1, 2 o 3): ").strip()

nivel_nombre = niveles_validos[nivel]

print(f"\n🎥 Presiona 'R' para grabar la secuencia '{etiqueta}' con nivel '{nivel_nombre}'.")
print("Presiona 'Q' para salir.")

# --- INICIALIZAR CÁMARA ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la cámara (índice 0).")

recording = False
buffer_sequence = []
frames_descartados = 0
countdown = 0

# --- LOOP PRINCIPAL ---
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("⚠️ No se pudo leer frame de la cámara.")
        break

    h, w, _ = frame.shape
    box_left = int(w / 2 - BOX_WIDTH / 2)
    box_top = int(h / 2 - BOX_HEIGHT / 2)
    box_right = int(w / 2 + BOX_WIDTH / 2)
    box_bottom = int(h / 2 + BOX_HEIGHT / 2)
    cv2.rectangle(frame, (box_left, box_top), (box_right, box_bottom), (0, 0, 255), 2)

    results = tracker.detect(frame)
    tracker.draw(frame, results)

    if countdown > 0:
        cv2.putText(frame, f"{countdown}", (w // 2 - 20, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 4, (0, 0, 255), 4)
        cv2.imshow("Grabador de Frases", frame)
        cv2.waitKey(1)
        time.sleep(1)
        countdown -= 1
        if countdown == 0:
            print("🎬 ¡Grabando!")
            recording = True
            buffer_sequence = []
            frames_descartados = 0

    elif recording:
        if len(buffer_sequence) < FRAMES_TOTAL:
            frame_vector = build_frame_vector(results)

            # Un frame sin manos no aporta informacion sobre la sena: antes solo
            # se comprobaba la varianza global, que la pose y la cara mantenian
            # alta aunque no se hubiera detectado ninguna mano.
            if not has_hands(frame_vector):
                print("❌ Frame descartado: no se detectaron manos")
                frames_descartados += 1
            else:
                buffer_sequence.append(frame_vector)
                print(f"✅ Frame {len(buffer_sequence)}/{FRAMES_TOTAL}")

            cv2.putText(frame, f"Grabando {len(buffer_sequence)}/{FRAMES_TOTAL}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("Grabador de Frases", frame)
            cv2.waitKey(1)
            time.sleep(1.0 / FPS)

        else:
            try:
                trimmed_sequence = buffer_sequence[FRAMES_TO_SKIP:]
                if len(trimmed_sequence) < FRAMES_TO_SAVE:
                    raise ValueError(f"Solo {len(trimmed_sequence)} frames válidos. Se necesitan {FRAMES_TO_SAVE}.")
                final_sequence = trimmed_sequence[:FRAMES_TO_SAVE]
                save_sequence(final_sequence, etiqueta, nivel_nombre)
                print(f"✅ Secuencia guardada con {len(final_sequence)} frames.")
                print(f"📉 Frames descartados: {frames_descartados}")
            except Exception as e:
                print(f"⚠️ Error al guardar: {e}")
            buffer_sequence = []
            frames_descartados = 0
            recording = False

    else:
        cv2.putText(frame, "Presiona 'R' para iniciar grabacion, 'Q' para salir",
                    (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("Grabador de Frases", frame)
        key = cv2.waitKeyEx(1)
        if key in (ord('q'), ord('Q')):
            print("⛔ Cerrando...")
            break
        if key in (ord('r'), ord('R')) and not recording and countdown == 0:
            print("⏳ Grabación iniciará en:")
            countdown = 3
        continue

    # Revisión de teclas
    key = cv2.waitKeyEx(1)
    if key in (ord('q'), ord('Q')):
        print("⛔ Cerrando...")
        break
    if key in (ord('r'), ord('R')) and not recording and countdown == 0:
        print("⏳ Grabación iniciará en:")
        countdown = 3

cap.release()
cv2.destroyAllWindows()
