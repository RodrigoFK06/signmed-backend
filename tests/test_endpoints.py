import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Provide dummy model_loader to avoid importing TensorFlow during tests
class DummyModel:
    def predict(self, x, verbose=0):
        return [[1.0]]

class DummyEncoder:
    def inverse_transform(self, arr):
        return ["test"]

sys.modules['app.services.model_loader'] = type('ML', (), {'model': DummyModel(), 'encoder': DummyEncoder()})()

# Provide dummy database layer so importing app.main does not require Motor/MongoDB
class DummyCollection:
    async def insert_one(self, doc):
        pass
    async def update_one(self, *a, **kw):
        pass
    async def find_one(self, filt):
        return {}
    def find(self, *a, **kw):
        class C:
            async def __aiter__(self):
                if False:
                    yield None
            def sort(self, *a, **kw):
                return self
            def skip(self, *a, **kw):
                return self
            def limit(self, *a, **kw):
                return self
        return C()
    def aggregate(self, *a, **kw):
        class C:
            async def to_list(self, length=None):
                return []
            async def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration
        return C()
    async def count_documents(self, f):
        return 0

sys.modules['app.db.mongodb'] = type('DB', (), {
    'collection': DummyCollection(),
    'stats_collection': DummyCollection(),
})()

from app.main import app


client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
