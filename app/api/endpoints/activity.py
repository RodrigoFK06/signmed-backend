from datetime import datetime, date, time, timezone
from typing import List

import logging
from fastapi import APIRouter, HTTPException, Path, Depends, Response

from app.db.mongodb import collection
from app.models.schema import DailyActivityRecord, DailyActivitySummary, DailyActivityResponse
from app.services.auth import get_current_user  # JWT → dict con {nickname, email, role}

# TODO: INDEXING - Consider an index on (nickname, timestamp) for optimal query performance in /activity/daily.
# TODO: TESTS - Add unit tests for date parsing, date range generation (including timezone handling), and aggregation of daily activity stats (mocking MongoDB).

logger = logging.getLogger(__name__)
router = APIRouter(tags=["User Activity"])

@router.get(
    "/activity/daily/{nickname}/{date_str}",
    response_model=DailyActivityResponse,
    summary="Get daily activity for a user",
    description=(
        "Retrieves a summary and detailed records of a user's practice activity for a specific day. "
        "Patients can only view their own activity; health workers may view any user's activity."
    ),
)
async def get_daily_activity(
    response: Response,
    nickname: str = Path(..., description="User's nickname or 'me' para el usuario autenticado", example="usuario123"),
    date_str: str = Path(..., description="Date in YYYY-MM-DD format", example="2023-10-28", regex=r"^\d{4}-\d{2}-\d{2}$"),
    current_user: dict = Depends(get_current_user),
):
    """
    Auth rules:
      - PATIENT: sólo puede consultar su propia actividad (nickname del JWT). Se acepta 'me' para conveniencia.
      - HEALTH_WORKER: puede consultar cualquier nickname.
    """
    # --- 1) Validar/parsear fecha ---
    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Invalid date format received: %s", date_str)
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # --- 2) Resolver usuario objetivo según rol ---
    role = (current_user or {}).get("role", "PATIENT")
    auth_nick = (current_user or {}).get("nickname") or (current_user or {}).get("email")

    target_nickname = auth_nick if nickname.lower() == "me" else nickname

    if role != "HEALTH_WORKER" and target_nickname != auth_nick:
        # Paciente intentando ver actividad de otro usuario
        raise HTTPException(status_code=403, detail="Forbidden: you can only view your own activity.")

    # --- 3) Rango de fecha (UTC) ---
    # MongoDB suele guardar en UTC; usamos el día completo en UTC
    start_datetime = datetime.combine(parsed_date, time.min).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(parsed_date, time.max).replace(tzinfo=timezone.utc)

    mongo_filter = {
        "nickname": target_nickname,
        "timestamp": {"$gte": start_datetime, "$lte": end_datetime},  # $lte para incluir fin de día
    }

    activity_records: List[DailyActivityRecord] = []
    total_practices = 0
    correct_practices = 0
    doubtful_practices = 0
    incorrect_practices = 0

    try:
        cursor = collection.find(mongo_filter).sort("timestamp", 1)  # ascendente por hora

        async for doc in cursor:
            total_practices += 1
            evaluation = doc.get("evaluation")
            if evaluation == "CORRECTO":
                correct_practices += 1
            elif evaluation == "DUDOSO":
                doubtful_practices += 1
            elif evaluation == "INCORRECTO":
                incorrect_practices += 1

            # Asegurar timestamp válido
            record_timestamp = doc.get("timestamp")
            if not isinstance(record_timestamp, datetime):
                logger.warning("Record with _id %s has invalid timestamp format.", str(doc.get("_id")))
                record_timestamp = datetime.fromtimestamp(0, tz=timezone.utc)
                doc["timestamp"] = record_timestamp

            # Normalizar _id → str (Pydantic usará alias en el modelo)
            doc["_id"] = str(doc.get("_id"))

            # Instanciar modelo (ignorará campos extra, mapeará alias)
            activity_records.append(DailyActivityRecord(**doc))

        # Resumen
        summary = DailyActivitySummary(
            total_practices=total_practices,
            correct_practices=correct_practices,
            doubtful_practices=doubtful_practices,
            incorrect_practices=incorrect_practices,
        )

        # Cabeceras
        response.headers["X-Total-Count"] = str(total_practices)
        response.headers["Cache-Control"] = "no-store"

        return DailyActivityResponse(
            nickname=target_nickname,
            date=date_str,
            summary=summary,
            records=activity_records,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error fetching daily activity for user '%s' on date '%s': %s",
            target_nickname, date_str, e, exc_info=True
        )
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching daily activity.")
