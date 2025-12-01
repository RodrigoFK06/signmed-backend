"""
Esquemas de datos para exámenes.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    """Tipos de preguntas."""
    MULTIPLE_CHOICE = "multiple_choice"
    SIGN_PRACTICE = "sign_practice"


class ExamDifficulty(str, Enum):
    """Niveles de dificultad del examen."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class MultipleChoiceQuestion(BaseModel):
    """Pregunta de opción múltiple."""
    question_text: str = Field(default="¿Qué seña es esta?", description="Texto de la pregunta")
    correct_label: str = Field(..., description="Label correcto (seña registrada)")
    options: List[str] = Field(..., description="Lista de opciones de respuesta (incluye la correcta)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_text": "¿Qué seña es esta?",
                "correct_label": "hola",
                "options": ["hola", "gracias", "adios", "por_favor"]
            }
        }


class SignPracticeQuestion(BaseModel):
    """Pregunta de práctica de señas."""
    question_text: str = Field(default="Realiza la siguiente seña", description="Texto de la pregunta")
    label_to_practice: str = Field(..., description="Label de la seña a practicar")
    min_confidence: float = Field(default=60.0, description="Confianza mínima requerida")
    max_attempts: int = Field(default=3, description="Número máximo de intentos")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_text": "Realiza la siguiente seña",
                "label_to_practice": "hola",
                "min_confidence": 60.0,
                "max_attempts": 3
            }
        }


class ExamQuestion(BaseModel):
    """Pregunta de examen (puede ser de cualquier tipo)."""
    question_type: QuestionType
    multiple_choice: Optional[MultipleChoiceQuestion] = None
    sign_practice: Optional[SignPracticeQuestion] = None
    order: int = Field(..., description="Orden de la pregunta en el examen")
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_type": "multiple_choice",
                "multiple_choice": {
                    "question_text": "¿Qué seña es esta?",
                    "correct_label": "hola",
                    "options": ["hola", "gracias", "adios", "por_favor"]
                },
                "order": 1
            }
        }


class ExamCreate(BaseModel):
    """Modelo para crear un examen."""
    title: str = Field(..., min_length=3, max_length=200, description="Título del examen")
    description: Optional[str] = Field(None, max_length=1000, description="Descripción del examen")
    difficulty: ExamDifficulty = Field(..., description="Nivel de dificultad del examen")
    questions: List[ExamQuestion] = Field(..., min_items=1, description="Lista de preguntas")
    passing_score: float = Field(default=60.0, ge=0, le=100, description="Puntuación mínima para aprobar")
    time_limit_minutes: Optional[int] = Field(None, gt=0, description="Límite de tiempo en minutos (opcional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Examen de Señas Básicas",
                "description": "Evaluación de conocimientos básicos de lengua de señas",
                "difficulty": "beginner",
                "questions": [
                    {
                        "question_type": "multiple_choice",
                        "multiple_choice": {
                            "question_text": "¿Qué seña es esta?",
                            "correct_label": "hola",
                            "options": ["hola", "gracias", "adios", "por_favor"]
                        },
                        "order": 1
                    },
                    {
                        "question_type": "sign_practice",
                        "sign_practice": {
                            "label_to_practice": "gracias",
                            "min_confidence": 60.0
                        },
                        "order": 2
                    }
                ],
                "passing_score": 60.0,
                "time_limit_minutes": 30
            }
        }


class ExamResponse(BaseModel):
    """Modelo de respuesta de examen."""
    id: str
    title: str
    description: Optional[str]
    difficulty: ExamDifficulty
    questions: List[ExamQuestion]
    passing_score: float
    time_limit_minutes: Optional[int]
    created_by: str  # User ID del admin que lo creó
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "title": "Examen de Señas Básicas",
                "description": "Evaluación de conocimientos básicos",
                "questions": [],
                "passing_score": 60.0,
                "time_limit_minutes": 30,
                "created_by": "507f191e810c19729de860ea",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "is_active": True
            }
        }


class ExamAttemptAnswer(BaseModel):
    """Respuesta de un usuario a una pregunta."""
    question_order: int
    question_type: QuestionType
    selected_option: Optional[str] = None  # Para multiple choice
    predicted_label: Optional[str] = None  # Para sign practice
    confidence: Optional[float] = None  # Para sign practice
    is_correct: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "question_order": 1,
                "question_type": "multiple_choice",
                "selected_option": "hola",
                "is_correct": True
            }
        }


class ExamAttemptCreate(BaseModel):
    """Modelo para registrar un intento de examen."""
    exam_id: str
    answers: List[ExamAttemptAnswer]
    
    class Config:
        json_schema_extra = {
            "example": {
                "exam_id": "507f1f77bcf86cd799439011",
                "answers": [
                    {
                        "question_order": 1,
                        "question_type": "multiple_choice",
                        "selected_option": "hola",
                        "is_correct": True
                    }
                ]
            }
        }


class ExamAttemptResponse(BaseModel):
    """Modelo de respuesta de intento de examen."""
    id: str
    exam_id: str
    user_id: str
    answers: List[ExamAttemptAnswer]
    score: float  # Porcentaje de respuestas correctas
    passed: bool
    started_at: datetime
    completed_at: datetime
    time_taken_minutes: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439012",
                "exam_id": "507f1f77bcf86cd799439011",
                "user_id": "507f191e810c19729de860ea",
                "answers": [],
                "score": 75.0,
                "passed": True,
                "started_at": "2024-01-15T14:00:00Z",
                "completed_at": "2024-01-15T14:25:00Z",
                "time_taken_minutes": 25.0
            }
        }
