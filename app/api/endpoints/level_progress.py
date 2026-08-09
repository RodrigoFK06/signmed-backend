"""
Progreso por nivel de dificultad.

Version anterior: `get_labels_by_difficulty()` leia el CSV de 135 MB con pandas
en cada llamada, desde dentro de un `async def`, lo que congelaba el event loop
completo durante segundos. Ademas `/increment-level` registraba cualquier
`label_id` que le enviaran ("TEMPORAL: Para debugging, aceptar cualquier
label"), de modo que un usuario podia inflar su progreso a voluntad.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from app.db.mongodb import get_collections
from app.services.auth import get_current_user
from app.services.labels import DIFFICULTIES, Difficulty, get_labels_by_difficulty

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/progress", tags=["Progress"])


class LevelProgress(BaseModel):
    level: str
    total_signs: int
    completed_signs: int
    percentage: float
    last_updated: Optional[datetime] = None


class IncrementLevelRequest(BaseModel):
    level: Difficulty = Field(..., description="beginner | intermediate | advanced")
    label_id: str = Field(..., min_length=1, description="Sena completada.")


class CompletedDifficultiesResponse(BaseModel):
    completed_difficulties: List[str]
    has_beginner: bool
    has_intermediate: bool
    has_advanced: bool


def _build_level_progress(level: Difficulty, stored: dict, catalog: Dict[str, List[str]]) -> LevelProgress:
    available = catalog.get(level, [])
    # Solo cuentan las senas que siguen existiendo en el catalogo: si se retira
    # una sena del modelo, el progreso historico no debe superar el 100 %.
    completed = [sign for sign in stored.get(level, {}).get("completed_signs", []) if sign in available]
    total = len(available)
    return LevelProgress(
        level=level,
        total_signs=total,
        completed_signs=len(completed),
        percentage=round(len(completed) / total * 100, 2) if total else 0.0,
        last_updated=stored.get(level, {}).get("last_updated"),
    )


@router.get(
    "/level-progress",
    response_model=Dict[str, LevelProgress],
    summary="Progreso del usuario por nivel",
)
async def get_level_progress(current_user: dict = Depends(get_current_user)):
    stored = current_user.get("level_progress", {}) or {}
    catalog = get_labels_by_difficulty()
    return {level: _build_level_progress(level, stored, catalog) for level in DIFFICULTIES}


@router.post(
    "/increment-level",
    response_model=LevelProgress,
    summary="Registrar una sena completada",
)
async def increment_level_progress(
    payload: IncrementLevelRequest,
    current_user: dict = Depends(get_current_user),
):
    catalog = get_labels_by_difficulty()
    available = catalog.get(payload.level, [])

    if payload.label_id not in available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La sena '{payload.label_id}' no pertenece al nivel '{payload.level}'.",
        )

    users = get_collections().users
    user_oid = ObjectId(str(current_user["_id"]))

    result = await users.find_one_and_update(
        {"_id": user_oid},
        {
            "$addToSet": {f"level_progress.{payload.level}.completed_signs": payload.label_id},
            "$set": {f"level_progress.{payload.level}.last_updated": datetime.now(tz=timezone.utc)},
        },
        return_document=ReturnDocument.AFTER,
    )

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    return _build_level_progress(payload.level, result.get("level_progress", {}) or {}, catalog)


@router.get(
    "/completed-difficulties",
    response_model=CompletedDifficultiesResponse,
    summary="Niveles con al menos una sena completada",
    description="Determina que examenes puede presentar el usuario.",
)
async def get_completed_difficulties(current_user: dict = Depends(get_current_user)):
    stored = current_user.get("level_progress", {}) or {}
    catalog = get_labels_by_difficulty()

    completed = [
        level
        for level in DIFFICULTIES
        if _build_level_progress(level, stored, catalog).completed_signs > 0
    ]

    return CompletedDifficultiesResponse(
        completed_difficulties=completed,
        has_beginner="beginner" in completed,
        has_intermediate="intermediate" in completed,
        has_advanced="advanced" in completed,
    )
