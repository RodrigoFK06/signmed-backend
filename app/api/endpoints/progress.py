from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from app.db.mongodb import collection
from app.models.schema import ProgressItem
from app.services.auth import get_current_user  # JWT → dict con {nickname, email, role}
import logging

# TODO: INDEXING - Consider an index on (nickname, expected_label, timestamp) or (expected_label, nickname, timestamp) to optimize the /progress aggregation, especially when filtered by nickname. Also, (timestamp) is used for last_attempt.
# TODO: TESTS - Add unit tests for the progress aggregation pipeline, covering different data scenarios (e.g., no data, data for one label, data for multiple labels, with/without nickname filter) and division by zero handling (mocking MongoDB).

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
    try:
        role = (current_user or {}).get("role", "PATIENT")
        current_user_id = str((current_user or {}).get("_id", ""))

        logger.info(f"[PROGRESS] Request from role={role}, current_user_id={current_user_id}, requested_user_id={user_id}")

        # Scope por rol
        match_stage = {}
        if role == "ADMIN":
            # Admin puede ver progreso de cualquier usuario si especifica user_id
            if user_id:
                match_stage["user_id"] = user_id
                logger.info(f"[PROGRESS] Admin viewing user_id={user_id}")
            # Si no especifica, ve su propio progreso
            else:
                match_stage["user_id"] = current_user_id
                logger.info(f"[PROGRESS] Admin viewing own progress")
        else:
            # Usuarios normales: solo su propio progreso
            match_stage["user_id"] = current_user_id
            logger.info(f"[PROGRESS] User viewing own progress")

        logger.info(f"[PROGRESS] MongoDB filter: {match_stage}")

        # Construcción del filtro con fallback para registros legacy
        # Si el registro no tiene user_id, intentar matchear por nickname (compatibilidad hacia atrás)
        if match_stage.get("user_id"):
            # Obtener el nickname del usuario para fallback
            from app.db.mongodb import users_collection
            from bson import ObjectId
            
            try:
                user_doc = await users_collection.find_one({"_id": ObjectId(match_stage["user_id"])})
                user_nickname = user_doc.get("nickname") if user_doc else None
                
                if user_nickname:
                    # Match por user_id O nickname (para registros legacy)
                    match_stage = {
                        "$or": [
                            {"user_id": match_stage["user_id"]},
                            {"nickname": user_nickname}
                        ]
                    }
                    logger.info(f"[PROGRESS] Using fallback filter with nickname={user_nickname}")
            except Exception as e:
                logger.warning(f"[PROGRESS] Could not fetch user nickname for fallback: {e}")

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

        cursor = collection.aggregate(pipeline)
        result: List[ProgressItem] = []
        async for doc in cursor:
            result.append(doc)

        if not result and user_id:
            logger.info("No progress data found for user_id: %s", user_id)
        elif not result:
            logger.info("No progress data found for current user: %s", current_user_id)

        return result

    except Exception as e:
        logger.error("Error calculating progress for user_id '%s': %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error al calcular progreso: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Error al obtener el progreso: {str(e)}")
