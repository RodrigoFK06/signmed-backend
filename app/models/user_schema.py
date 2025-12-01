from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field

# Roles y estados de usuario
UserRole = Literal["HEALTH_WORKER", "PATIENT", "ADMIN"]
UserStatus = Literal["pending", "approved", "rejected"]

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str
    role: UserRole
    document_url: Optional[str] = None  # URL del documento PDF (solo para HEALTH_WORKER)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    nickname: str
    role: UserRole
    status: UserStatus = "approved"  # Los pacientes son aprobados por defecto
    created_at: datetime
    document_url: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None