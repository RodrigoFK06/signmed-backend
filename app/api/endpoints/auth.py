from fastapi import APIRouter, HTTPException, Depends, status
from datetime import timedelta, datetime
from bson import ObjectId
from app.db.mongodb import users_collection
from app.models.schema import UserCreate, UserLogin, UserPublic, Token
from app.services.auth import (
    hash_password, verify_password, create_access_token, get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=UserPublic, status_code=201)
async def signup(data: UserCreate):
    try:
        # Validaciones de unicidad
        if await users_collection.find_one({"email": data.email.lower()}):
            raise HTTPException(status_code=400, detail="El email ya está registrado")
        if await users_collection.find_one({"nickname": data.nickname}):
            raise HTTPException(status_code=400, detail="El nickname ya está en uso")

        # Determinar estado según el rol
        # Los pacientes son aprobados automáticamente
        # Los trabajadores de salud requieren aprobación
        status_value = "approved" if data.role == "PATIENT" else "pending"

        # Documento a insertar (incluye role y status)
        doc = {
            "email": data.email.lower(),
            "password_hash": hash_password(data.password),
            "nickname": data.nickname,
            "role": data.role,
            "status": status_value,
            "document_url": data.document_url,  # URL del documento PDF
            "created_at": datetime.utcnow(),
        }

        res = await users_collection.insert_one(doc)

        return {
            "id": str(res.inserted_id),
            "email": doc["email"],
            "nickname": doc["nickname"],
            "role": doc["role"],
            "status": doc["status"],
            "document_url": doc.get("document_url"),
            "created_at": doc["created_at"],
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    user = await users_collection.find_one({"email": data.email.lower()})
    if not user or not verify_password(data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    # Verificar el estado del usuario
    user_status = user.get("status", "approved")
    if user_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Tu cuenta está pendiente de aprobación. Por favor espera a que un administrador revise tu solicitud."
        )
    elif user_status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu solicitud ha sido rechazada. Por favor contacta con el administrador."
        )

    # Role por defecto si no existe (backfill lógico)
    role = user.get("role", "PATIENT")

    # Incluir claims útiles en el JWT
    claims = {
        "sub": str(user["_id"]),
        "email": user["email"],
        "nickname": user.get("nickname", ""),
        "role": role,
        "status": user_status,
    }

    access_token = create_access_token(claims, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)):
    # current_user proviene del JWT decodificado + fetch, asegurar role por defecto
    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "nickname": current_user["nickname"],
        "role": current_user.get("role", "PATIENT"),
        "status": current_user.get("status", "approved"),
        "document_url": current_user.get("document_url"),
        "created_at": current_user.get("created_at"),
        "approved_at": current_user.get("approved_at"),
        "rejected_at": current_user.get("rejected_at"),
    }
