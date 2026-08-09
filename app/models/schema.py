from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from app.core.settings import settings
from app.services.labels import get_label_ids

FRAMES = settings.sequence_frames
FEATURES = settings.sequence_features


# --- Predicción (request/response) ---
class PredictRequest(BaseModel):
    sequence: List[List[float]] = Field(
        ...,
        description=f"Secuencia de keypoints: exactamente {FRAMES} frames de {FEATURES} valores.",
    )
    expected_label: Optional[str] = Field(
        default=None,
        examples=["tengo_fiebre_y_mareo"],
        description="Sena que el usuario intentaba realizar. Si se omite, la evaluacion sera DUDOSO.",
    )
    nickname: Optional[str] = Field(
        default=None,
        examples=["usuario123"],
        description="Alias opcional. El backend prioriza siempre el nickname del JWT.",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: List[List[float]]) -> List[List[float]]:
        if len(value) != FRAMES:
            raise ValueError(
                f"La secuencia debe tener exactamente {FRAMES} frames, se recibieron {len(value)}."
            )

        for index, frame in enumerate(value, start=1):
            if len(frame) != FEATURES:
                raise ValueError(
                    f"Cada frame debe tener {FEATURES} valores; el frame {index} tiene {len(frame)}. "
                    "Revisa que el cliente use el extractor de landmarks vigente."
                )

        return value

    @field_validator("expected_label")
    @classmethod
    def validate_label(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        normalized = value.strip().lower()
        known = get_label_ids()
        # Si no hay artefactos cargados (entorno sin modelo) no se bloquea la peticion.
        if known and normalized not in known:
            raise ValueError(
                f"La etiqueta '{normalized}' no existe. Etiquetas validas: {', '.join(sorted(known))}."
            )
        return normalized


class PredictEvaluation(BaseModel):
    expected: Optional[str] = Field(None, description="Etiqueta que el usuario intentaba realizar.")
    final: str = Field(..., description="Veredicto: CORRECTO, DUDOSO o INCORRECTO.")


class BackendPredictResponse(BaseModel):
    """Respuesta del servicio de inferencia."""
    label: str = Field(..., description="Etiqueta predicha (orden del encoder).", examples=["dolor"])
    confidence: float = Field(..., description="Confianza en porcentaje (0-100).", examples=[95.5])
    probabilities: List[float] = Field(..., description="Probabilidades (0-1) de todas las clases.")
    evaluation: PredictEvaluation
    nickname: Optional[str] = Field(None, description="Alias del usuario que realizo el intento.")


# (Si más adelante expones una respuesta 'UI', puedes mantener este modelo también)
class PredictResponse(BaseModel):
    predicted_label: str = Field(..., description="La etiqueta predicha por el modelo.", examples=["dolor_de_cabeza"])
    confidence: float = Field(..., description="La confianza de la predicción, en porcentaje (0-100).", examples=[95.5])
    evaluation: str = Field(
        ...,
        description="Evaluación de la predicción (CORRECTO, DUDOSO, INCORRECTO).",
        examples=["CORRECTO"],
    )
    expected_label: Optional[str] = Field(  # 👈 nuevo (opcional)
        None,
        description="Etiqueta esperada enviada por el cliente (si se proporcionó en el request).",
        examples=["dolor_de_cabeza"],
    )
    observation: Optional[str] = Field(
        None,
        description="Observación adicional, especialmente si la evaluación es INCORRECTO (puede incluir sugerencias).",
        examples=["Intenta separar más los movimientos."],
    )
    success_rate: Optional[float] = Field(
        None, description="Tasa de éxito histórica para la etiqueta esperada (y usuario, si se proporcionó), en porcentaje.", examples=[75.0]
    )
    average_confidence: Optional[float] = Field(
        None, description="Confianza promedio histórica para la etiqueta esperada (y usuario, si se proporcionó), en porcentaje.", examples=[82.3]
    )


# --- Progreso / Actividad ---
class ProgressItem(BaseModel):
    label: str = Field(..., examples=["tengo_fiebre_y_tos"], description="Etiqueta de la seña evaluada")
    total_attempts: int = Field(..., examples=[10], description="Número total de intentos")
    correct_attempts: int = Field(..., examples=[7], description="Número de aciertos (evaluación == 'CORRECTO')")
    doubtful_attempts: int = Field(..., examples=[2], description="Número de intentos evaluados como 'DUDOSO'")
    incorrect_attempts: int = Field(..., examples=[1], description="Número de errores (evaluación == 'INCORRECTO')")

    success_rate: float = Field(..., examples=[70.0], description="Porcentaje de aciertos")
    doubtful_rate: float = Field(..., examples=[20.0], description="Porcentaje de evaluaciones dudosas")
    incorrect_rate: float = Field(..., examples=[10.0], description="Porcentaje de errores")

    average_confidence: float = Field(..., examples=[83.25], description="Confianza promedio")
    max_confidence: float = Field(..., examples=[92.5], description="Confianza máxima")
    min_confidence: float = Field(..., examples=[60.0], description="Confianza mínima")

    last_attempt: Optional[datetime] = Field(
        None,
        examples=["2025-05-20T22:32:10.123Z"],
        description="Fecha del último intento",
    )


class DailyActivityRecord(BaseModel):
    id: str = Field(..., alias="_id", description="El ID del registro de MongoDB", examples=["60d5ec49f0b2f3a1c4d4a9c1"])
    timestamp: datetime = Field(..., description="Fecha y hora completa del registro de la práctica", examples=["2023-10-26T10:30:00.123Z"])
    predicted_label: str = Field(..., description="Etiqueta predicha por el modelo", examples=["dolor_de_cabeza"])
    expected_label: str = Field(..., description="Etiqueta esperada por el usuario", examples=["dolor_de_cabeza"])
    confidence: float = Field(..., description="Confianza de la predicción (0-100)", examples=[92.75])
    evaluation: str = Field(..., description="Evaluación de la práctica (CORRECTO, DUDOSO, INCORRECTO)", examples=["CORRECTO"])


class DailyActivitySummary(BaseModel):
    total_practices: int = Field(..., description="Número total de prácticas realizadas en el día", examples=[25])
    correct_practices: int = Field(..., description="Número de prácticas evaluadas como 'CORRECTO'", examples=[18])
    doubtful_practices: int = Field(..., description="Número de prácticas evaluadas como 'DUDOSO'", examples=[5])
    incorrect_practices: int = Field(..., description="Número de prácticas evaluadas como 'INCORRECTO'", examples=[2])


class DailyActivityResponse(BaseModel):
    nickname: str = Field(..., description="Nickname del usuario", examples=["usuario_activo_123"])
    date: str = Field(..., description="Fecha de la actividad solicitada, en formato YYYY-MM-DD", examples=["2023-10-26"])
    summary: DailyActivitySummary = Field(..., description="Resumen de la actividad del día")
    records: List[DailyActivityRecord] = Field(..., description="Lista de registros de actividad para el día")


class GlobalResultDistributionItem(BaseModel):
    evaluation_type: str = Field(..., description="Type of evaluation (e.g., CORRECTO, DUDOSO, INCORRECTO)", examples=["CORRECTO"])
    count: int = Field(..., description="Total count for this evaluation type", examples=[1500])
    percentage: float = Field(..., description="Percentage of this evaluation type out of the total evaluations", examples=[75.0])


class GlobalResultsDistributionResponse(BaseModel):
    total_evaluations: int = Field(..., description="Total number of evaluations processed in the system", examples=[2000])
    distribution: List[GlobalResultDistributionItem] = Field(..., description="List of counts and percentages per evaluation type")


# --- Auth / Usuarios (con roles) ---
UserRole = Literal["HEALTH_WORKER", "PATIENT", "ADMIN"]
UserStatus = Literal["pending", "approved", "rejected"]

# Roles que un visitante puede pedir al registrarse. ADMIN queda deliberadamente
# fuera: antes `UserCreate.role` aceptaba todo el `UserRole`, de modo que
# cualquiera podia enviar {"role": "ADMIN"} en /auth/signup y crear una cuenta
# de administrador. Los administradores se provisionan con scripts/create_admin.py.
SelfAssignableRole = Literal["PATIENT", "HEALTH_WORKER"]

Nickname = Annotated[str, StringConstraints(min_length=2, max_length=32, strip_whitespace=True)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserCreate(BaseModel):
    email: EmailStr
    password: Password
    nickname: Nickname
    role: SelfAssignableRole = "PATIENT"
    document_url: Optional[str] = None  # URL del documento PDF (solo para HEALTH_WORKER)

    @field_validator("document_url")
    @classmethod
    def validate_document_url(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.startswith(("/uploads/", "http://", "https://")):
            raise ValueError("document_url debe ser una ruta de subida o una URL absoluta.")
        return value


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
