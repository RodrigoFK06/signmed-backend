from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status
from typing import List
from datetime import datetime
from bson import ObjectId

from app.db.mongodb import users_collection
from app.models.schema import UserRole
from app.services.auth import get_current_user
from app.services.authorize import require_role

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", response_model=List[dict])
async def get_all_users(current_user: dict = Depends(require_role("ADMIN"))):
    """Obtener lista de todos los usuarios del sistema"""
    all_users = await users_collection.find(
        {},
        {"password_hash": 0}  # No incluir la contraseña
    ).to_list(length=None)
    
    # Convertir ObjectId a string y preparar respuesta
    result = []
    for user in all_users:
        user_dict = {
            "_id": str(user["_id"]),
            "email": user.get("email"),
            "nickname": user.get("nickname"),
            "role": user.get("role"),
            "approved": user.get("status") == "approved" or user.get("role") in ["PATIENT", "ADMIN"],
            "status": user.get("status", "approved"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
        }
        result.append(user_dict)
    
    return result

@router.get("/pending-health-workers", response_model=List[dict])
async def get_pending_health_workers(current_user: dict = Depends(require_role("ADMIN"))):
    """Obtener lista de trabajadores de salud pendientes de aprobación"""
    pending_users = await users_collection.find(
        {"role": "HEALTH_WORKER", "status": "pending"},
        {"password_hash": 0}
    ).to_list(length=None)
    
    # Convertir ObjectId a string para evitar errores de serialización
    result = []
    for user in pending_users:
        user_dict = {
            "id": str(user["_id"]),
            "email": user.get("email"),
            "nickname": user.get("nickname"),
            "role": user.get("role"),
            "status": user.get("status"),
            "document_url": user.get("document_url"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None,
        }
        result.append(user_dict)
    
    return result

@router.post("/approve-health-worker/{user_id}")
async def approve_health_worker(
    user_id: str,
    current_user: dict = Depends(require_role("ADMIN"))
):
    """Aprobar un trabajador de salud pendiente"""
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id), "role": "HEALTH_WORKER", "status": "pending"},
        {"$set": {"status": "approved", "approved_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o ya aprobado")
    
    return {"message": "Usuario aprobado exitosamente"}

@router.post("/reject-health-worker/{user_id}")
async def reject_health_worker(
    user_id: str,
    current_user: dict = Depends(require_role("ADMIN"))
):
    """Rechazar un trabajador de salud pendiente"""
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id), "role": "HEALTH_WORKER", "status": "pending"},
        {"$set": {"status": "rejected", "rejected_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o ya procesado")
    
    return {"message": "Usuario rechazado exitosamente"}