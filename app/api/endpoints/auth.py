import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.settings import settings
from app.db.mongodb import get_collections
from app.models.schema import Token, UserCreate, UserLogin, UserPublic
from app.services.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


def _to_public(user: dict) -> dict:
    return {
        "id": str(user.get("_id", user.get("id", ""))),
        "email": user["email"],
        "nickname": user["nickname"],
        "role": user.get("role", "PATIENT"),
        "status": user.get("status", "approved"),
        "document_url": user.get("document_url"),
        "created_at": user.get("created_at"),
        "approved_at": user.get("approved_at"),
        "rejected_at": user.get("rejected_at"),
    }


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate):
    """
    Registra una cuenta.

    Los pacientes quedan aprobados al instante; el personal de salud queda en
    `pending` hasta que un administrador revise su documentacion. El rol ADMIN no
    es autoasignable (ver `SelfAssignableRole` en `app.models.schema`).
    """
    users = get_collections().users

    if data.role == "HEALTH_WORKER" and not data.document_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El personal de salud debe adjuntar un documento acreditativo.",
        )

    document = {
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "nickname": data.nickname,
        "role": data.role,
        "status": "approved" if data.role == "PATIENT" else "pending",
        "document_url": data.document_url,
        "created_at": datetime.now(tz=timezone.utc),
    }

    try:
        # La unicidad la garantiza el indice unico de MongoDB, no una consulta
        # previa: comprobar-y-luego-insertar deja una ventana en la que dos altas
        # simultaneas con el mismo email pasan las dos.
        result = await users.insert_one(document)
    except DuplicateKeyError as exc:
        field = "email" if "email" in str(exc) else "nickname"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cuenta con ese {field}.",
        ) from exc

    document["_id"] = result.inserted_id
    logger.info("Alta de usuario %s con rol %s", document["email"], document["role"])
    return _to_public(document)


@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    users = get_collections().users
    user = await users.find_one({"email": data.email.lower()})

    if not user or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
        )

    user_status = user.get("status", "approved")
    if user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta esta pendiente de aprobacion. Espera a que un administrador revise tu solicitud.",
        )
    if user_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud ha sido rechazada. Contacta con el administrador.",
        )

    token = create_access_token(
        {
            "sub": str(user["_id"]),
            "email": user["email"],
            "nickname": user.get("nickname", ""),
            "role": user.get("role", "PATIENT"),
        },
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)):
    return _to_public(current_user)
