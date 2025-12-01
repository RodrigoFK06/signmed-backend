import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.models import schema


def test_sequence_length_validation(monkeypatch):
    monkeypatch.setattr(schema, "VALID_LABELS", ["lbl"])
    seq = [[0.0]*42 for _ in range(35)]
    data = schema.PredictRequest(sequence=seq, expected_label="lbl")
    assert len(data.sequence) == 35


def test_invalid_frame_length(monkeypatch):
    monkeypatch.setattr(schema, "VALID_LABELS", ["lbl"])
    seq = [[0.0]*40 for _ in range(35)]
    with pytest.raises(ValueError):
        schema.PredictRequest(sequence=seq, expected_label="lbl")


def test_invalid_label(monkeypatch):
    monkeypatch.setattr(schema, "VALID_LABELS", ["lbl"])
    seq = [[0.0]*42 for _ in range(35)]
    with pytest.raises(ValueError):
        schema.PredictRequest(sequence=seq, expected_label="bad")
