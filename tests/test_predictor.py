import sys
import os
from types import SimpleNamespace

import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.models import schema

# Stub out the MongoDB layer so predictor can be imported without motor.
class DummyCollection:
    def __init__(self):
        self.inserted = []
        self.stats = {}

    async def insert_one(self, doc):
        self.inserted.append(doc)

    async def update_one(self, filt, update, upsert=False):
        stat = self.stats.setdefault((filt.get("expected_label"), filt.get("nickname")), {"total": 0, "correct": 0, "confidence_sum": 0.0})
        inc = update.get("$inc", {})
        stat["total"] += inc.get("total", 0)
        stat["correct"] += inc.get("correct", 0)
        stat["confidence_sum"] += inc.get("confidence_sum", 0.0)

    async def find_one(self, filt):
        return self.stats.get((filt.get("expected_label"), filt.get("nickname")), {"total": 0, "correct": 0, "confidence_sum": 0.0})

sys.modules['app.db.mongodb'] = SimpleNamespace(
    collection=DummyCollection(),
    stats_collection=DummyCollection(),
)


def make_dummy_model(expected_idx=0):
    class M:
        def predict(self, x, verbose=0):
            arr = [[0.0] * 3]
            arr[0][expected_idx] = 1.0
            return arr
    return M()


def make_dummy_encoder(label="label"):
    class E:
        def inverse_transform(self, arr):
            return [label]
    return E()


@pytest.mark.asyncio
async def test_predict_sequence_correct(monkeypatch):
    sys.modules['app.services.model_loader'] = SimpleNamespace(model=make_dummy_model(), encoder=make_dummy_encoder("test"))
    import importlib
    predictor = importlib.import_module('app.services.predictor')

    monkeypatch.setattr(schema, "VALID_LABELS", ["test"])

    dummy_collection = DummyCollection()
    monkeypatch.setattr(predictor, "collection", dummy_collection)
    monkeypatch.setattr(predictor, "stats_collection", dummy_collection)

    seq = [[0.0] * 42 for _ in range(35)]
    req = schema.PredictRequest(sequence=seq, expected_label="test")
    resp = await predictor.predict_sequence(req)
    assert resp.evaluation == "CORRECTO"
    assert resp.success_rate == 100.0
    assert dummy_collection.inserted
