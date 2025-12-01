from fastapi import Depends, HTTPException, status
from typing import Literal
from app.services.auth import get_current_user

UserRole = Literal["HEALTH_WORKER", "PATIENT", "ADMIN"]

def require_role(*allowed: UserRole):
    async def _inner(user = Depends(get_current_user)):
        role = user.get("role", "PATIENT")
        if role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user
    return _inner
