import cv2
import mediapipe as mp

class HolisticTracker:
    def __init__(self, detection_conf=0.5, tracking_conf=0.5, face_step=10):
        self.mp_holistic = mp.solutions.holistic
        self.holistic = self.mp_holistic.Holistic(
            min_detection_confidence=detection_conf,
            min_tracking_confidence=tracking_conf
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.face_step = face_step  # cada cuántos puntos se dibuja

    def detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self.holistic.process(rgb)

    def draw(self, frame, results):
        # Dibuja pose completa
        self.mp_draw.draw_landmarks(
            frame, results.pose_landmarks, self.mp_holistic.POSE_CONNECTIONS
        )

        # Dibuja manos completas
        for hand_landmarks in [results.left_hand_landmarks, results.right_hand_landmarks]:
            if hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_holistic.HAND_CONNECTIONS
                )

        # Dibuja solo algunos puntos de la cara (cada 10)
        if results.face_landmarks:
            for i, lm in enumerate(results.face_landmarks.landmark):
                if i % self.face_step == 0:  # saltar cada 10
                    h, w, _ = frame.shape
                    x, y = int(lm.x * w), int(lm.y * h)
                    cv2.circle(frame, (x, y), 1, (0, 0, 255), -1)
