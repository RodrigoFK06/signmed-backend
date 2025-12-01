import numpy as np

class DataProcessor:
    def normalize_landmarks(self, landmarks):
        """
        Normaliza los landmarks de una mano centrando en la muñeca
        y escalando a [-1, 1] basado en la mano más extendida.
        """
        if not landmarks or len(landmarks) != 21:
            return [0.0] * 42

        landmarks_array = np.array(landmarks, dtype=np.float32)

        # Centro (muñeca)
        base_x, base_y = landmarks_array[0]
        centered = landmarks_array - [base_x, base_y]

        # Escalar basado en la distancia máxima desde la muñeca
        distances = np.linalg.norm(centered, axis=1)
        max_dist = np.max(distances)
        if max_dist < 1.0:
            max_dist = 1.0  # evita división absurda

        normalized = centered / max_dist
        return normalized.flatten().tolist()

    def extract_xy_landmarks(self, hand_landmarks):
        landmarks = []
        for lm in hand_landmarks.landmark:
            landmarks.extend([lm.x, lm.y])
        return landmarks

