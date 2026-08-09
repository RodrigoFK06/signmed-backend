"""
Fixtures compartidas.

Los tests anteriores inyectaban un doble de `app.services.model_loader`, un
modulo que el camino de produccion ni siquiera importaba, y un doble de
`app.db.mongodb` al que le faltaban la mitad de las colecciones, asi que
`from app.main import app` fallaba. Aqui se sustituyen las dependencias reales
por los mecanismos que la propia aplicacion expone (`set_collections`,
`dependency_overrides`), sin parchear `sys.modules`.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.db.mongodb import Collections, set_collections  # noqa: E402


@pytest.fixture
def collections() -> Collections:
    """Colecciones respaldadas por una base de datos en memoria."""
    db = AsyncMongoMockClient()["signmed_test"]
    fake = Collections(
        predictions=db["predictions"],
        prediction_stats=db["prediction_stats"],
        users=db["users"],
        exams=db["exams"],
        exam_attempts=db["exam_attempts"],
    )
    set_collections(fake)
    yield fake
    set_collections(None)


@pytest.fixture
def app_client(collections):
    """Cliente HTTP con la base de datos simulada ya instalada."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_client(app_client, collections):
    """Cliente con un usuario paciente autenticado."""
    from app.main import app
    from app.services.auth import get_current_user

    user = {
        "_id": "6570f1f77bcf86cd79943901",
        "id": "6570f1f77bcf86cd79943901",
        "email": "paciente@example.com",
        "nickname": "paciente",
        "role": "PATIENT",
        "status": "approved",
        "created_at": datetime.now(tz=timezone.utc),
    }

    app.dependency_overrides[get_current_user] = lambda: user
    yield app_client, user
    app.dependency_overrides.clear()
