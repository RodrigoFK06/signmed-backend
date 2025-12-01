# TODO: INDEXING - Consider compound indexes on (nickname, timestamp), (evaluation, timestamp) and (timestamp) for optimal query performance in /records.
# TODO: TESTS - Add unit tests for filter construction logic and pagination (mocking MongoDB).

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, Depends

from app.db.mongodb import collection
# ⬇️ JWT → dict con al menos {nickname, email, role}
from app.services.auth import get_current_user

router = APIRouter()

@router.get("/records", tags=["Registros"])
async def get_records(
    response: Response,
    user_id: Optional[str] = Query(None, description="Filter by user ID (solo ADMIN)"),
    date_from: Optional[datetime] = Query(None, description="Filter records from this date (ISO). Ej: 2023-01-01T00:00:00Z"),
    date_to: Optional[datetime] = Query(None, description="Filter records up to this date (ISO). Ej: 2023-01-31T23:59:59Z"),
    evaluation: Optional[str] = Query(None, description="Filter by evaluation type: CORRECTO, DUDOSO, INCORRECTO", regex="^(CORRECTO|DUDOSO|INCORRECTO)$"),
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return per page"),
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieves a paginated and filterable list of prediction records.

    Auth rules:
    - PATIENT: sólo ve sus propios registros (forzado a su user_id del JWT).
    - ADMIN: puede ver global o filtrar por ?user_id=...
    """
    try:
        role = (current_user or {}).get("role", "PATIENT")
        current_user_id = str((current_user or {}).get("_id", ""))

        mongo_filter = {}

        # Scope por rol
        if role == "ADMIN":
            # Admin puede filtrar por user_id, o ver todos si no se provee
            if user_id:
                mongo_filter["user_id"] = user_id
        else:
            # Usuario normal: siempre sus propios registros (ignora query user_id)
            mongo_filter["user_id"] = current_user_id

        # Fechas → asegurar tz aware (UTC)
        if date_from and date_to:
            if date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            if date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)
            mongo_filter["timestamp"] = {"$gte": date_from, "$lte": date_to}
        elif date_from:
            if date_from.tzinfo is None:
                date_from = date_from.replace(tzinfo=timezone.utc)
            mongo_filter["timestamp"] = {"$gte": date_from}
        elif date_to:
            if date_to.tzinfo is None:
                date_to = date_to.replace(tzinfo=timezone.utc)
            mongo_filter["timestamp"] = {"$lte": date_to}

        if evaluation:
            mongo_filter["evaluation"] = evaluation

        total_count = await collection.count_documents(mongo_filter)

        cursor = (
            collection.find(mongo_filter)
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )

        registros = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            # timestamp → ISO string
            ts = doc.get("timestamp")
            if isinstance(ts, datetime):
                doc["timestamp"] = ts.isoformat()
            registros.append(doc)

        response.headers["X-Total-Count"] = str(total_count)
        response.headers["Cache-Control"] = "no-store"
        return registros

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar los registros: {str(e)}")
