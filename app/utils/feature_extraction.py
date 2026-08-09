"""
Definicion del vector de features de un frame.

Este modulo es la unica fuente de verdad sobre que contiene cada una de las 150
posiciones del vector, y debe mantenerse sincronizado con el extractor del
frontend (`lib/landmarks.ts`).

## El fallo que corrige

El grabador original construia el vector asi:

    pose (33 landmarks -> 66 valores)
    + cara (468[::10] = 47 landmarks -> 94 valores)
    + manos (42 landmarks -> 84 valores)
    -> se truncaba con frame_vector[:150]

66 + 94 = 160, ya por encima de 150. **Las manos quedaban siempre fuera del
recorte.** Un modelo de lengua de senas se entreno sin ver las manos: aprendio la
postura del cuerpo y la posicion de la cara. Ademas el contenido de las
posiciones cambiaba segun si MediaPipe detectaba la cara o no (sin cara, si
entraban las manos), asi que la misma posicion del vector significaba cosas
distintas en frames distintos.

Se comprobo sobre `data/dataset_medico.csv`: la posicion 66 vale (0.389, 0.573),
practicamente la nariz (0.394, 0.529), y no ninguna de las dos munecas
((0.634, 0.933) y (0.310, 0.952)). El bloque [66:150] ademas apenas se mueve
(desviacion temporal 0.0037 frente a 0.0276 del bloque de pose), justo lo que se
espera de una cara y no de unas manos gesticulando.

## El layout corregido

Las manos van primero y con hueco garantizado; la pose se recorta al tren
superior (los landmarks 23-32 son piernas y pies, que en una webcam quedan fuera
de cuadro y MediaPipe extrapola con valores de hasta y=2.9, puro ruido).

    [  0: 84]  mano izquierda (21) + mano derecha (21), (x, y)
    [ 84:130]  pose, tren superior: landmarks 0-22, (x, y)
    [130:150]  cara: 10 puntos de referencia, (x, y)

Un landmark ausente se rellena con 0.0 y su bloque conserva siempre el mismo
tamano, de modo que cada posicion significa siempre lo mismo.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

# --- Tamanos de cada bloque (en valores, no en landmarks) ---
HAND_LANDMARKS = 21
HANDS_SIZE = 2 * HAND_LANDMARKS * 2  # 84

POSE_UPPER_BODY_LANDMARKS = 23  # 0-22: cara, hombros, brazos, munecas, caderas
POSE_SIZE = POSE_UPPER_BODY_LANDMARKS * 2  # 46

# Puntos faciales estables para captar orientacion y gesto sin inflar el vector.
FACE_KEY_POINTS = (1, 33, 61, 199, 263, 291, 13, 14, 152, 10)
FACE_SIZE = len(FACE_KEY_POINTS) * 2  # 20

FEATURES_PER_FRAME = HANDS_SIZE + POSE_SIZE + FACE_SIZE  # 150

HANDS_SLICE = slice(0, HANDS_SIZE)
POSE_SLICE = slice(HANDS_SIZE, HANDS_SIZE + POSE_SIZE)
FACE_SLICE = slice(HANDS_SIZE + POSE_SIZE, FEATURES_PER_FRAME)

assert FEATURES_PER_FRAME == 150, "El modelo espera 150 features por frame."


def _flatten(landmarks: Optional[Iterable], indices: Optional[Iterable[int]], expected: int) -> List[float]:
    """Aplana (x, y) de los landmarks pedidos, rellenando con ceros si faltan."""
    if landmarks is None:
        return [0.0] * expected

    points = list(landmarks)
    selected = points if indices is None else [
        points[i] if i < len(points) else None for i in indices
    ]

    values: List[float] = []
    for point in selected:
        if point is None:
            values.extend((0.0, 0.0))
        else:
            values.extend((float(point.x), float(point.y)))

    if len(values) < expected:
        values.extend([0.0] * (expected - len(values)))
    return values[:expected]


def build_frame_vector(results) -> List[float]:
    """
    Construye el vector de 150 features a partir de un resultado de MediaPipe
    Holistic. `results` es lo que devuelve `HolisticTracker.detect()`.
    """
    left = getattr(results, "left_hand_landmarks", None)
    right = getattr(results, "right_hand_landmarks", None)
    pose = getattr(results, "pose_landmarks", None)
    face = getattr(results, "face_landmarks", None)

    vector: List[float] = []
    vector += _flatten(left.landmark if left else None, None, HAND_LANDMARKS * 2)
    vector += _flatten(right.landmark if right else None, None, HAND_LANDMARKS * 2)
    vector += _flatten(pose.landmark if pose else None, range(POSE_UPPER_BODY_LANDMARKS), POSE_SIZE)
    vector += _flatten(face.landmark if face else None, FACE_KEY_POINTS, FACE_SIZE)

    assert len(vector) == FEATURES_PER_FRAME
    return vector


def has_hands(frame_vector: List[float]) -> bool:
    """True si el frame contiene al menos una mano detectada."""
    return any(value != 0.0 for value in frame_vector[HANDS_SLICE])
