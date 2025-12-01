# TODO: TESTS - Add unit tests for Pydantic model validators, especially for PredictRequest sequence and label validation.
from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional, Literal

import pandas as pd
from pydantic import BaseModel, EmailStr, Field, validator, constr

from app.config import DATASET_PATH


# --- Etiquetas válidas (desde CSV) ---
def load_labels() -> List[str]:
    dataset_path = str(DATASET_PATH)
    if not os.path.exists(dataset_path):
        return []
    df = pd.read_csv(dataset_path, header=None)
    label_col = df.columns[-2]
    return df[label_col].dropna().unique().tolist()


VALID_LABELS = [s.strip().lower() for s in load_labels()]


# --- Predicción (request/response) ---
class PredictRequest(BaseModel):
    sequence: List[List[float]] = Field(
        ...,
        example=[[0.0] * 150] * 35,  # ejemplo con Holistic (35x150)
        description="Sequence of keypoints: exactly 35 frames with either 42 or 150 features each.",
    )
    expected_label: str = Field(
        ...,
        example="tengo_fiebre_y_tos",
        description="The expected medical sign label for this sequence.",
    )
    nickname: Optional[str] = Field(
        None, example="usuario123", description="Optional user's nickname for tracking purposes."
    )

    # Campo derivado para que el servicio sepa si llegó 42 o 150 (excluido de I/O)
    feature_dim: Optional[Literal[42, 150]] = Field(default=None, exclude=True)

    @validator("sequence")
    def validate_sequence(cls, value: List[List[float]]) -> List[List[float]]:
        # Deben ser 35 frames exactos (el modelo está entrenado con 35)
        if not isinstance(value, list) or len(value) != 35:
            n = len(value) if isinstance(value, list) else "n/a"
            raise ValueError(f"La secuencia debe tener exactamente 35 frames, pero se recibieron {n}.")

        # Todos los frames deben tener el mismo tamaño y ser 42 o 150
        first_len = len(value[0]) if value and isinstance(value[0], list) else None
        if first_len not in (42, 150):
            raise ValueError(
                f"Cada frame debe tener exactamente 42 o 150 valores (keypoints), "
                f"pero se encontró un frame con {first_len} valores."
            )

        for idx, frame in enumerate(value, start=1):
            if len(frame) != first_len:
                raise ValueError(
                    f"Todos los frames deben tener el mismo tamaño ({first_len}). "
                    f"El frame {idx} tiene {len(frame)} valores."
                )
            # Coerción a float con control de errores
            for i, val in enumerate(frame):
                try:
                    frame[i] = float(val)
                except Exception:
                    raise ValueError(f"Valor no convertible a float en frame {idx}, índice {i}: {val!r}")

        return value

    @validator("expected_label")
    def validate_label(cls, value: str) -> str:
        norm = value.strip().lower()
        if VALID_LABELS and norm not in VALID_LABELS:
            # Mensaje amigable (muestra algunas etiquetas válidas)
            sample = ", ".join(VALID_LABELS[:10]) + ("..." if len(VALID_LABELS) > 10 else "")
            raise ValueError(
                f"La etiqueta '{norm}' no es válida. Use una etiqueta conocida. "
                f"Algunas válidas: {sample}"
            )
        return norm


class BackendPredictResponse(BaseModel):
    """
    Respuesta 'cruda' del backend (lo que devuelve el servicio predictor).
    El frontend la mapeará a su contrato UI si hace falta.
    """
    label: str = Field(..., description="Etiqueta predicha por el modelo (orden del encoder).", example="dolor_de_cabeza")
    confidence: float = Field(..., description="Confianza en 0–100 (porcentaje).", example=95.5)
    probabilities: List[float] = Field(..., description="Vector de probabilidades (0–1) para todas las clases.")
    evaluation: Optional[dict] = Field(
        default=None,
        description='Información adicional, p.ej. {"expected": "<label esperada>"}',
        example={"expected": "dolor_de_cabeza"},
    )


# (Si más adelante expones una respuesta 'UI', puedes mantener este modelo también)
class PredictResponse(BaseModel):
    predicted_label: str = Field(..., description="La etiqueta predicha por el modelo.", example="dolor_de_cabeza")
    confidence: float = Field(..., description="La confianza de la predicción, en porcentaje (0-100).", example=95.5)
    evaluation: str = Field(
        ...,
        description="Evaluación de la predicción (CORRECTO, DUDOSO, INCORRECTO).",
        example="CORRECTO",
    )
    expected_label: Optional[str] = Field(  # 👈 nuevo (opcional)
        None,
        description="Etiqueta esperada enviada por el cliente (si se proporcionó en el request).",
        example="dolor_de_cabeza",
    )
    observation: Optional[str] = Field(
        None,
        description="Observación adicional, especialmente si la evaluación es INCORRECTO (puede incluir sugerencias).",
        example="Intenta separar más los movimientos.",
    )
    success_rate: Optional[float] = Field(
        None, description="Tasa de éxito histórica para la etiqueta esperada (y usuario, si se proporcionó), en porcentaje.", example=75.0
    )
    average_confidence: Optional[float] = Field(
        None, description="Confianza promedio histórica para la etiqueta esperada (y usuario, si se proporcionó), en porcentaje.", example=82.3
    )


# --- Progreso / Actividad ---
class ProgressItem(BaseModel):
    label: str = Field(..., example="tengo_fiebre_y_tos", description="Etiqueta de la seña evaluada")
    total_attempts: int = Field(..., example=10, description="Número total de intentos")
    correct_attempts: int = Field(..., example=7, description="Número de aciertos (evaluación == 'CORRECTO')")
    doubtful_attempts: int = Field(..., example=2, description="Número de intentos evaluados como 'DUDOSO'")
    incorrect_attempts: int = Field(..., example=1, description="Número de errores (evaluación == 'INCORRECTO')")

    success_rate: float = Field(..., example=70.0, description="Porcentaje de aciertos")
    doubtful_rate: float = Field(..., example=20.0, description="Porcentaje de evaluaciones dudosas")
    incorrect_rate: float = Field(..., example=10.0, description="Porcentaje de errores")

    average_confidence: float = Field(..., example=83.25, description="Confianza promedio")
    max_confidence: float = Field(..., example=92.5, description="Confianza máxima")
    min_confidence: float = Field(..., example=60.0, description="Confianza mínima")

    last_attempt: Optional[datetime] = Field(
        None,
        example="2025-05-20T22:32:10.123Z",
        description="Fecha del último intento",
    )


class DailyActivityRecord(BaseModel):
    id: str = Field(..., alias="_id", description="El ID del registro de MongoDB", example="60d5ec49f0b2f3a1c4d4a9c1")
    timestamp: datetime = Field(..., description="Fecha y hora completa del registro de la práctica", example="2023-10-26T10:30:00.123Z")
    predicted_label: str = Field(..., description="Etiqueta predicha por el modelo", example="dolor_de_cabeza")
    expected_label: str = Field(..., description="Etiqueta esperada por el usuario", example="dolor_de_cabeza")
    confidence: float = Field(..., description="Confianza de la predicción (0-100)", example=92.75)
    evaluation: str = Field(..., description="Evaluación de la práctica (CORRECTO, DUDOSO, INCORRECTO)", example="CORRECTO")


class DailyActivitySummary(BaseModel):
    total_practices: int = Field(..., description="Número total de prácticas realizadas en el día", example=25)
    correct_practices: int = Field(..., description="Número de prácticas evaluadas como 'CORRECTO'", example=18)
    doubtful_practices: int = Field(..., description="Número de prácticas evaluadas como 'DUDOSO'", example=5)
    incorrect_practices: int = Field(..., description="Número de prácticas evaluadas como 'INCORRECTO'", example=2)


class DailyActivityResponse(BaseModel):
    nickname: str = Field(..., description="Nickname del usuario", example="usuario_activo_123")
    date: str = Field(..., description="Fecha de la actividad solicitada, en formato YYYY-MM-DD", example="2023-10-26")
    summary: DailyActivitySummary = Field(..., description="Resumen de la actividad del día")
    records: List[DailyActivityRecord] = Field(..., description="Lista de registros de actividad para el día")


class GlobalResultDistributionItem(BaseModel):
    evaluation_type: str = Field(..., description="Type of evaluation (e.g., CORRECTO, DUDOSO, INCORRECTO)", example="CORRECTO")
    count: int = Field(..., description="Total count for this evaluation type", example=1500)
    percentage: float = Field(..., description="Percentage of this evaluation type out of the total evaluations", example=75.0)


class GlobalResultsDistributionResponse(BaseModel):
    total_evaluations: int = Field(..., description="Total number of evaluations processed in the system", example=2000)
    distribution: List[GlobalResultDistributionItem] = Field(..., description="List of counts and percentages per evaluation type")


# --- Auth / Usuarios (con roles) ---
UserRole = Literal["HEALTH_WORKER", "PATIENT", "ADMIN"]
UserStatus = Literal["pending", "approved", "rejected"]


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: constr(min_length=2, max_length=32)
    role: UserRole = "PATIENT"
    document_url: Optional[str] = None  # URL del documento PDF (solo para HEALTH_WORKER)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    nickname: str
    role: UserRole
    status: UserStatus = "approved"
    created_at: datetime
    document_url: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[UserRole] = None
