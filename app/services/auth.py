"""
Autenticacion basada en JWT.

`SECRET_KEY` ya no tiene un valor por defecto que funcione en produccion: antes
era `"dev_secret_change_me"`, publicado en el repositorio, de modo que cualquiera
podia firmar un token valido para cualquier usuario si la variable de entorno no
estaba definida. `app.core.settings` falla al arrancar si eso ocurre fuera de
desarrollo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import settings
from app.db.mongodb import get_collections

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        # Sin hash almacenado no hay nada que verificar, pero se gasta el mismo
        # tiempo que en un fallo normal para no filtrar si el email existe.
        pwd_context.dummy_verify()
        return False
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Firma un token. `data` debe incluir al menos `sub`, `email`, `nickname` y `role`."""
    to_encode = data.copy()
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


async def get_user_by_email(email: str) -> Optional[dict]:
    return await get_collections().users.find_one({"email": email.lower()})


async def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    return await get_collections().users.find_one({"_id": oid})


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    user_id = payload.get("sub")
    if not user_id:
        raise CREDENTIALS_EXCEPTION

    user = await get_user_by_id(user_id)
    if not user:
        raise CREDENTIALS_EXCEPTION

    # El rol se toma siempre del documento en base de datos, nunca del token: si
    # un administrador degrada a un usuario, su JWT vigente no debe conservar
    # los permisos antiguos.
    if user.get("status") in {"pending", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta no esta activa.",
        )

    user["id"] = str(user["_id"])
    user.setdefault("role", "PATIENT")
    user.pop("password_hash", None)
    return user
