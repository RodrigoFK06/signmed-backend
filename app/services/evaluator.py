from typing import Tuple


def evaluate_prediction(predicted_label: str, expected_label: str, confidence: float, threshold: float = 75.0) -> Tuple[str, bool]:
    """Return evaluation label and correctness boolean."""
    if predicted_label.lower() == expected_label.lower():
        evaluation = "CORRECTO" if confidence >= threshold else "DUDOSO"
        correct = evaluation == "CORRECTO"
    else:
        evaluation = "INCORRECTO"
        correct = False
    return evaluation, correct
