from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongodb import get_collections
from app.models.schema import ProgressItem
from app.services.auth import get_current_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get(
    "/progress",
    response_model=List[ProgressItem],
    tags=["Registros"],
    summary="Get user progress statistics per label",
    description="Aggregated progress stats por etiqueta. Filtrado por user_id."
)
async def get_progress(
    user_id: Optional[str] = Query(None, description="Filtrar por user_id (solo ADMIN)"),
    current_user: dict = Depends(get_current_user),
):
    collection = get_collections().predictions
    try:
        role = (current_user or {}).get("role", "PATIENT")
        current_user_id = str((current_user or {}).get("_id", ""))

        # Solo un ADMIN puede consultar el progreso de otra persona.
        target_user_id = user_id if (role == "ADMIN" and user_id) else current_user_id
        match_stage: dict = {"user_id": target_user_id}

        # Los registros anteriores a la migracion a `user_id` solo guardaban el
        # nickname; se incluyen para que el historial no aparezca vacio.
        legacy_nickname = (current_user or {}).get("nickname") if target_user_id == current_user_id else None
        if legacy_nickname:
            match_stage = {"$or": [{"user_id": target_user_id}, {"nickname": legacy_nickname}]}

        logger.debug("Progreso solicitado por %s (rol %s) sobre %s", current_user_id, role, target_user_id)

        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {
                "$group": {
                    "_id": "$expected_label",
                    "total_attempts": {"$sum": 1},
                    "correct_attempts": {
                        "$sum": {"$cond": [{"$eq": ["$evaluation", "CORRECTO"]}, 1, 0]}
                    },
                    "doubtful_attempts": {
                        "$sum": {"$cond": [{"$eq": ["$evaluation", "DUDOSO"]}, 1, 0]}
                    },
                    "incorrect_attempts": {
                        "$sum": {"$cond": [{"$eq": ["$evaluation", "INCORRECTO"]}, 1, 0]}
                    },
                    "average_confidence": {"$avg": "$confidence"},
                    "max_confidence": {"$max": "$confidence"},
                    "min_confidence": {"$min": "$confidence"},
                    "last_attempt": {"$max": "$timestamp"}
                }
            },
            {
                "$project": {
                    "label": "$_id",
                    "total_attempts": 1,
                    "correct_attempts": 1,
                    "doubtful_attempts": 1,
                    "incorrect_attempts": 1,
                    "success_rate": {
                        "$cond": {
                            "if": {"$eq": ["$total_attempts", 0]},
                            "then": 0.0,
                            "else": {
                                "$round": [
                                    {"$multiply": [{"$divide": ["$correct_attempts", "$total_attempts"]}, 100]},
                                    2
                                ]
                            }
                        }
                    },
                    "doubtful_rate": {
                        "$cond": {
                            "if": {"$eq": ["$total_attempts", 0]},
                            "then": 0.0,
                            "else": {
                                "$round": [
                                    {"$multiply": [{"$divide": ["$doubtful_attempts", "$total_attempts"]}, 100]},
                                    2
                                ]
                            }
                        }
                    },
                    "incorrect_rate": {
                        "$cond": {
                            "if": {"$eq": ["$total_attempts", 0]},
                            "then": 0.0,
                            "else": {
                                "$round": [
                                    {"$multiply": [{"$divide": ["$incorrect_attempts", "$total_attempts"]}, 100]},
                                    2
                                ]
                            }
                        }
                    },
                    "average_confidence": {"$round": ["$average_confidence", 2]},
                    "max_confidence": {"$round": ["$max_confidence", 2]},
                    "min_confidence": {"$round": ["$min_confidence", 2]},
                    "last_attempt": 1,
                    "_id": 0
                }
            },
            {"$sort": {"label": 1}}
        ]

        result: List[ProgressItem] = [doc async for doc in collection.aggregate(pipeline)]
        if not result:
            logger.info("Sin datos de progreso para %s", target_user_id)
        return result

    except Exception:
        logger.exception("Error calculando el progreso de %s", target_user_id)
        raise HTTPException(status_code=500, detail="Error al calcular el progreso.")
