"""
Acceso a MongoDB.

El modulo anterior abria el cliente y lanzaba `RuntimeError` en tiempo de
importacion si faltaba `MONGO_URI`, de modo que importar cualquier endpoint (o
recolectar los tests) exigia una base de datos. Aqui el cliente se crea de forma
perezosa y los tests pueden inyectar un doble con `set_collections`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.settings import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Collections:
    predictions: AsyncIOMotorCollection
    prediction_stats: AsyncIOMotorCollection
    users: AsyncIOMotorCollection
    exams: AsyncIOMotorCollection
    exam_attempts: AsyncIOMotorCollection


_client: Optional[AsyncIOMotorClient] = None
_collections: Optional[Collections] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri, uuidRepresentation="standard")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


def get_collections() -> Collections:
    global _collections
    if _collections is None:
        db = get_database()
        _collections = Collections(
            predictions=db["predictions"],
            prediction_stats=db["prediction_stats"],
            users=db["users"],
            exams=db["exams"],
            exam_attempts=db["exam_attempts"],
        )
    return _collections


def set_collections(collections: Optional[Collections]) -> None:
    """Sustituye las colecciones (tests). `None` restaura el comportamiento real."""
    global _collections
    _collections = collections


async def create_indexes() -> None:
    """
    Crea los indices que necesitan las consultas de la API.

    Sin ellos, `/records`, `/progress` y `/activity/daily` hacen un COLLSCAN por
    peticion; las restricciones unicas sobre `users` eliminan ademas la condicion
    de carrera del registro, donde dos altas simultaneas con el mismo email
    pasaban la comprobacion previa y se insertaban las dos.
    """
    collections = get_collections()

    await collections.users.create_index("email", unique=True)
    await collections.users.create_index("nickname", unique=True)
    await collections.users.create_index([("role", 1), ("status", 1)])

    await collections.predictions.create_index([("user_id", 1), ("timestamp", -1)])
    await collections.predictions.create_index([("nickname", 1), ("timestamp", -1)])
    await collections.predictions.create_index([("user_id", 1), ("expected_label", 1)])
    await collections.predictions.create_index("evaluation")

    await collections.prediction_stats.create_index(
        [("user_id", 1), ("expected_label", 1)], unique=True
    )

    await collections.exams.create_index([("is_active", 1), ("created_at", -1)])
    await collections.exam_attempts.create_index([("exam_id", 1), ("completed_at", -1)])
    await collections.exam_attempts.create_index([("user_id", 1), ("completed_at", -1)])

    logger.info("Indices de MongoDB verificados.")


async def close_client() -> None:
    global _client, _collections
    if _client is not None:
        _client.close()
        _client = None
    _collections = None
