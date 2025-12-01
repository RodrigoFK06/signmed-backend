"""
Endpoints para gestión de exámenes.
Solo los administradores pueden crear/editar/eliminar exámenes.
Todos los usuarios autenticados pueden ver y realizar exámenes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import logging

from app.models.exam_schema import (
    ExamCreate,
    ExamResponse,
    ExamAttemptCreate,
    ExamAttemptResponse,
    QuestionType
)
from app.db.mongodb import exams_collection, exam_attempts_collection
from app.services.authorize import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exams", tags=["Exams"])


def exam_doc_to_response(doc: dict) -> dict:
    """Convierte un documento de MongoDB a formato de respuesta."""
    doc["id"] = str(doc.pop("_id"))
    if "created_at" in doc and isinstance(doc["created_at"], datetime):
        doc["created_at"] = doc["created_at"].isoformat()
    if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
        doc["updated_at"] = doc["updated_at"].isoformat()
    return doc


def attempt_doc_to_response(doc: dict) -> dict:
    """Convierte un documento de intento a formato de respuesta."""
    doc["id"] = str(doc.pop("_id"))
    doc["exam_id"] = str(doc["exam_id"])
    doc["user_id"] = str(doc["user_id"])
    if "started_at" in doc and isinstance(doc["started_at"], datetime):
        doc["started_at"] = doc["started_at"].isoformat()
    if "completed_at" in doc and isinstance(doc["completed_at"], datetime):
        doc["completed_at"] = doc["completed_at"].isoformat()
    return doc


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam: ExamCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Crear un nuevo examen.
    Solo administradores pueden crear exámenes.
    """
    # Verificar que sea administrador
    role = current_user.get("role", "")
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden crear exámenes"
        )
    
    user_id = str(current_user.get("_id", ""))
    
    # Validar que las preguntas tengan el contenido correcto según su tipo
    for q in exam.questions:
        if q.question_type == QuestionType.MULTIPLE_CHOICE:
            if not q.multiple_choice:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: Falta contenido de opción múltiple"
                )
            # Validar que la respuesta correcta esté en las opciones
            if q.multiple_choice.correct_label not in q.multiple_choice.options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: La respuesta correcta '{q.multiple_choice.correct_label}' debe estar en las opciones"
                )
        
        elif q.question_type == QuestionType.SIGN_PRACTICE:
            if not q.sign_practice:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: Falta contenido de práctica de señas"
                )
    
    # Crear documento de examen
    now = datetime.utcnow()
    exam_doc = {
        "title": exam.title,
        "description": exam.description,
        "difficulty": exam.difficulty.value,
        "questions": [q.model_dump() for q in exam.questions],
        "passing_score": exam.passing_score,
        "time_limit_minutes": exam.time_limit_minutes,
        "created_by": user_id,
        "created_at": now,
        "updated_at": now,
        "is_active": True
    }
    
    result = await exams_collection.insert_one(exam_doc)
    exam_doc["_id"] = result.inserted_id
    
    logger.info(f"✅ Examen creado: {exam.title} por admin {user_id}")
    
    return exam_doc_to_response(exam_doc)


@router.get("/", response_model=List[ExamResponse])
async def list_exams(
    include_inactive: bool = False,
    difficulty: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Listar todos los exámenes disponibles.
    Por defecto solo muestra exámenes activos.
    Puede filtrar por dificultad (beginner, intermediate, advanced).
    """
    query = {}
    if not include_inactive:
        query["is_active"] = True
    
    if difficulty:
        query["difficulty"] = difficulty
    
    exams = []
    async for doc in exams_collection.find(query).sort("created_at", -1):
        exams.append(exam_doc_to_response(doc))
    
    return exams


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obtener detalles de un examen específico.
    """
    try:
        exam = await exams_collection.find_one({"_id": ObjectId(exam_id)})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen inválido: {exam_id}"
        )
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen no encontrado"
        )
    
    return exam_doc_to_response(exam)


@router.put("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    exam: ExamCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Actualizar un examen existente.
    Solo administradores pueden editar exámenes.
    """
    # Verificar que sea administrador
    role = current_user.get("role", "")
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden editar exámenes"
        )
    
    try:
        exam_oid = ObjectId(exam_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen inválido: {exam_id}"
        )
    
    # Validar preguntas igual que en create
    for q in exam.questions:
        if q.question_type == QuestionType.MULTIPLE_CHOICE:
            if not q.multiple_choice:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: Falta contenido de opción múltiple"
                )
            if q.multiple_choice.correct_label not in q.multiple_choice.options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: La respuesta correcta debe estar en las opciones"
                )
        elif q.question_type == QuestionType.SIGN_PRACTICE:
            if not q.sign_practice:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {q.order}: Falta contenido de práctica de señas"
                )
    
    # Actualizar documento
    update_doc = {
        "title": exam.title,
        "description": exam.description,
        "difficulty": exam.difficulty.value,
        "questions": [q.model_dump() for q in exam.questions],
        "passing_score": exam.passing_score,
        "time_limit_minutes": exam.time_limit_minutes,
        "updated_at": datetime.utcnow()
    }
    
    result = await exams_collection.update_one(
        {"_id": exam_oid},
        {"$set": update_doc}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen no encontrado"
        )
    
    updated_exam = await exams_collection.find_one({"_id": exam_oid})
    logger.info(f"✅ Examen actualizado: {exam_id}")
    
    return exam_doc_to_response(updated_exam)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Eliminar (desactivar) un examen.
    Solo administradores pueden eliminar exámenes.
    """
    # Verificar que sea administrador
    role = current_user.get("role", "")
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden eliminar exámenes"
        )
    
    try:
        exam_oid = ObjectId(exam_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen inválido: {exam_id}"
        )
    
    # Soft delete - solo marcar como inactivo
    result = await exams_collection.update_one(
        {"_id": exam_oid},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen no encontrado"
        )
    
    logger.info(f"🗑️ Examen desactivado: {exam_id}")


@router.post("/{exam_id}/attempts", response_model=ExamAttemptResponse, status_code=status.HTTP_201_CREATED)
async def submit_exam_attempt(
    exam_id: str,
    attempt: ExamAttemptCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Registrar un intento de examen completado.
    """
    user_id = str(current_user.get("_id", ""))
    
    # Verificar que el examen existe
    try:
        exam = await exams_collection.find_one({"_id": ObjectId(exam_id), "is_active": True})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen inválido: {exam_id}"
        )
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen no encontrado o inactivo"
        )
    
    # Calcular puntuación comparando respuestas con las correctas del examen
    exam_questions = exam["questions"]
    total_questions = len(exam_questions)
    correct_answers = 0
    
    # Crear un diccionario para mapear respuestas por orden
    answers_by_order = {a.question_order: a for a in attempt.answers}
    
    for question in exam_questions:
        q_order = question["order"]
        user_answer = answers_by_order.get(q_order)
        
        if not user_answer:
            continue
            
        # Verificar respuesta según el tipo de pregunta
        if question["question_type"] == "multiple_choice":
            correct_label = question["multiple_choice"]["correct_label"]
            if user_answer.selected_option == correct_label:
                correct_answers += 1
                user_answer.is_correct = True
            else:
                user_answer.is_correct = False
                
        elif question["question_type"] == "sign_practice":
            # Para práctica de señas, verificar el label predicho
            expected_label = question["sign_practice"]["label_to_practice"]
            min_confidence = question["sign_practice"].get("min_confidence", 60.0)
            
            if (user_answer.predicted_label == expected_label and 
                user_answer.confidence and user_answer.confidence >= min_confidence):
                correct_answers += 1
                user_answer.is_correct = True
            else:
                user_answer.is_correct = False
    
    score = correct_answers
    percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    passed = percentage >= exam["passing_score"]
    
    # Calcular tiempo tomado
    now = datetime.utcnow()
    # Asumimos que started_at se envía desde el frontend, sino usar now - time_limit
    started_at = now  # Esto debería venir del frontend
    time_taken = 0.0  # Esto debería calcularse en el frontend
    
    # Crear documento de intento
    attempt_doc = {
        "exam_id": ObjectId(exam_id),
        "user_id": ObjectId(user_id),
        "answers": [a.model_dump() for a in attempt.answers],
        "score": score,
        "passed": passed,
        "started_at": started_at,
        "completed_at": now,
        "time_taken_minutes": time_taken
    }
    
    result = await exam_attempts_collection.insert_one(attempt_doc)
    attempt_doc["_id"] = result.inserted_id
    
    logger.info(f"📝 Intento de examen registrado: usuario {user_id}, examen {exam_id}, puntuación {percentage:.1f}% ({correct_answers}/{total_questions})")
    
    return attempt_doc_to_response(attempt_doc)


@router.get("/{exam_id}/attempts", response_model=List[dict])
async def list_exam_attempts(
    exam_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Listar intentos de un examen con información del usuario.
    Usuarios normales solo ven sus propios intentos.
    Administradores ven todos los intentos.
    """
    from app.db.mongodb import users_collection
    
    user_id = str(current_user.get("_id", ""))
    role = current_user.get("role", "")
    
    try:
        exam_oid = ObjectId(exam_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen inválido: {exam_id}"
        )
    
    query = {"exam_id": exam_oid}
    
    # Si no es admin, solo mostrar sus intentos
    if role != "ADMIN":
        query["user_id"] = ObjectId(user_id)
    
    attempts_with_users = []
    async for attempt_doc in exam_attempts_collection.find(query).sort("completed_at", -1):
        attempt_user_id = attempt_doc.get("user_id")
        
        # Intentar buscar por ObjectId
        user = await users_collection.find_one({"_id": attempt_user_id})
        
        # Si no encuentra, intentar convertir a string y buscar
        if not user and isinstance(attempt_user_id, ObjectId):
            user = await users_collection.find_one({"_id": str(attempt_user_id)})
        
        # Si aún no encuentra, intentar convertir string a ObjectId y buscar
        if not user and isinstance(attempt_user_id, str):
            try:
                user = await users_collection.find_one({"_id": ObjectId(attempt_user_id)})
            except:
                pass
        
        # Log para depuración
        if not user:
            logger.warning(f"⚠️ Usuario no encontrado para user_id: {attempt_user_id} (tipo: {type(attempt_user_id)})")
        else:
            logger.info(f"✅ Usuario encontrado: {user.get('nickname')} para user_id: {attempt_user_id}")
        
        attempt_data = attempt_doc_to_response(attempt_doc.copy())
        attempt_data["user_info"] = {
            "nickname": user.get("nickname", "Usuario desconocido") if user else "Usuario desconocido",
            "email": user.get("email", "N/A") if user else "N/A",
            "role": user.get("role", "") if user else ""
        }
        
        attempts_with_users.append(attempt_data)
    
    return attempts_with_users


@router.get("/attempts/my-attempts", response_model=List[ExamAttemptResponse])
async def list_my_attempts(
    current_user: dict = Depends(get_current_user)
):
    """
    Listar todos los intentos del usuario actual.
    """
    user_id = str(current_user.get("_id", ""))
    
    attempts = []
    async for doc in exam_attempts_collection.find({"user_id": ObjectId(user_id)}).sort("completed_at", -1):
        attempts.append(attempt_doc_to_response(doc))
    
    return attempts
