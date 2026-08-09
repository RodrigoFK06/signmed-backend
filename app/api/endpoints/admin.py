"""Panel de administracion: alta y revision de personal de salud."""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.db.mongodb import get_collections
from app.services.authorize import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


class AdminUser(BaseModel):
    id: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    role: Optional[str] = None
    status: str = "approved"
    document_url: Optional[str] = None
    created_at: Optional[datetime] = None


def _to_admin_user(user: dict) -> AdminUser:
    return AdminUser(
        id=str(user["_id"]),
        email=user.get("email"),
        nickname=user.get("nickname"),
        role=user.get("role"),
        status=user.get("status", "approved"),
        document_url=user.get("document_url"),
        created_at=user.get("created_at"),
    )


def _parse_object_id(user_id: str) -> ObjectId:
    try:
        return ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Identificador de usuario invalido: {user_id}",
        ) from exc


@router.get("/users", response_model=List[AdminUser], summary="Listar todos los usuarios")
async def get_all_users(_: dict = Depends(require_role("ADMIN"))):
    users = await get_collections().users.find({}, {"password_hash": 0}).to_list(length=None)
    return [_to_admin_user(user) for user in users]


@router.get(
    "/pending-health-workers",
    response_model=List[AdminUser],
    summary="Listar el personal de salud pendiente de aprobacion",
)
async def get_pending_health_workers(_: dict = Depends(require_role("ADMIN"))):
    users = await get_collections().users.find(
        {"role": "HEALTH_WORKER", "status": "pending"},
        {"password_hash": 0},
    ).to_list(length=None)
    return [_to_admin_user(user) for user in users]


async def _set_status(user_id: str, new_status: str, timestamp_field: str) -> dict:
    result = await get_collections().users.update_one(
        {"_id": _parse_object_id(user_id), "role": "HEALTH_WORKER", "status": "pending"},
        {"$set": {"status": new_status, timestamp_field: datetime.now(tz=timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay ninguna solicitud pendiente con ese identificador.",
        )
    logger.info("Solicitud de personal de salud %s -> %s", user_id, new_status)
    return {"message": f"Usuario {new_status}", "status": new_status}


@router.post("/approve-health-worker/{user_id}", summary="Aprobar personal de salud")
async def approve_health_worker(user_id: str, _: dict = Depends(require_role("ADMIN"))):
    return await _set_status(user_id, "approved", "approved_at")


@router.post("/reject-health-worker/{user_id}", summary="Rechazar personal de salud")
async def reject_health_worker(user_id: str, _: dict = Depends(require_role("ADMIN"))):
    return await _set_status(user_id, "rejected", "rejected_at")