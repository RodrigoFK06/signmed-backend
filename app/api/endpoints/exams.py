"""
Endpoints para gestión de exámenes.
Solo los administradores pueden crear/editar/eliminar exámenes.
Todos los usuarios autenticados pueden ver y realizar exámenes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone
import logging

from app.models.exam_schema import (
    ExamCreate,
    ExamResponse,
    ExamAttemptCreate,
    ExamAttemptResponse,
    QuestionType
)
from app.db.mongodb import get_collections
from app.services.authorize import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exams", tags=["Exams"])


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _require_admin(current_user: dict, action: str) -> str:
    """Comprueba el rol y devuelve el id del administrador."""
    if current_user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Solo los administradores pueden {action} examenes",
        )
    return str(current_user.get("_id", ""))


def _parse_exam_id(exam_id: str) -> ObjectId:
    try:
        return ObjectId(exam_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID de examen invalido: {exam_id}",
        ) from exc


def _validate_questions(exam: ExamCreate) -> None:
    """Valida coherencia entre el tipo de pregunta y su contenido."""
    seen_orders: set[int] = set()

    for question in exam.questions:
        if question.order in seen_orders:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hay dos preguntas con el mismo orden ({question.order}).",
            )
        seen_orders.add(question.order)

        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            if not question.multiple_choice:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Pregunta {question.order}: falta el contenido de opcion multiple",
                )
            if question.multiple_choice.correct_label not in question.multiple_choice.options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Pregunta {question.order}: la respuesta correcta "
                        f"'{question.multiple_choice.correct_label}' debe estar entre las opciones"
                    ),
                )
        elif question.question_type == QuestionType.SIGN_PRACTICE and not question.sign_practice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pregunta {question.order}: falta el contenido de practica de senas",
            )


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
    for field in ("started_at", "completed_at"):
        if isinstance(doc.get(field), datetime):
            doc[field] = doc[field].isoformat()

    # Los intentos anteriores a la separacion score/percentage solo guardaban el
    # conteo de aciertos; se deriva el porcentaje para no romper la respuesta.
    if "percentage" not in doc:
        answered = len(doc.get("answers", []))
        score = doc.get("score", 0)
        doc["percentage"] = round(score / answered * 100, 2) if answered else 0.0

    return doc


@router.post("/", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam: ExamCreate,
    current_user: dict = Depends(get_current_user)
):
    """Crear un nuevo examen. Solo administradores."""
    user_id = _require_admin(current_user, "crear")
    _validate_questions(exam)

    now = _now()
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
    
    result = await get_collections().exams.insert_one(exam_doc)
    exam_doc["_id"] = result.inserted_id

    logger.info("Examen creado: %s por el administrador %s", exam.title, user_id)
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
    async for doc in get_collections().exams.find(query).sort("created_at", -1):
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
    exam = await get_collections().exams.find_one({"_id": _parse_exam_id(exam_id)})

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
    _require_admin(current_user, "editar")
    exam_oid = _parse_exam_id(exam_id)
    _validate_questions(exam)

    update_doc = {
        "title": exam.title,
        "description": exam.description,
        "difficulty": exam.difficulty.value,
        "questions": [q.model_dump() for q in exam.questions],
        "passing_score": exam.passing_score,
        "time_limit_minutes": exam.time_limit_minutes,
        "updated_at": _now(),
    }

    result = await get_collections().exams.update_one(
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
    _require_admin(current_user, "eliminar")
    exam_oid = _parse_exam_id(exam_id)

    # Borrado logico: los intentos historicos deben seguir apuntando al examen.
    result = await get_collections().exams.update_one(
        {"_id": exam_oid},
        {"$set": {"is_active": False, "updated_at": _now()}}
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examen no encontrado"
        )

    logger.info("Examen desactivado: %s", exam_id)


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
    collections = get_collections()

    exam = await collections.exams.find_one({"_id": _parse_exam_id(exam_id), "is_active": True})

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

    # El inicio lo marca el cliente al abrir el examen. Antes se fijaba
    # `started_at = now` y `time_taken = 0.0` con un comentario de "esto deberia
    # venir del frontend", asi que todos los intentos se guardaban con duracion
    # cero. Si el cliente no lo envia, se deja en None en lugar de inventarlo.
    now = _now()
    started_at = attempt.started_at
    if started_at is not None and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    time_taken = round((now - started_at).total_seconds() / 60, 2) if started_at else None

    attempt_doc = {
        "exam_id": ObjectId(exam_id),
        "user_id": ObjectId(user_id),
        "answers": [a.model_dump() for a in attempt.answers],
        "score": score,
        "percentage": round(percentage, 2),
        "passed": passed,
        "started_at": started_at or now,
        "completed_at": now,
        "time_taken_minutes": time_taken,
    }

    result = await collections.exam_attempts.insert_one(attempt_doc)
    attempt_doc["_id"] = result.inserted_id

    logger.info(
        "Intento registrado: usuario=%s examen=%s puntuacion=%.1f%% (%d/%d)",
        user_id, exam_id, percentage, correct_answers, total_questions,
    )
    
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
    collections = get_collections()
    user_id = str(current_user.get("_id", ""))
    role = current_user.get("role", "")
    exam_oid = _parse_exam_id(exam_id)

    query: dict = {"exam_id": exam_oid}
    if role != "ADMIN":
        query["user_id"] = ObjectId(user_id)

    attempts = [doc async for doc in collections.exam_attempts.find(query).sort("completed_at", -1)]

    # Una sola consulta para todos los autores en lugar de una (o tres) por
    # intento. Los documentos antiguos guardaban `user_id` como cadena, asi que
    # se buscan ambas representaciones a la vez.
    raw_ids = {doc.get("user_id") for doc in attempts if doc.get("user_id") is not None}
    lookup_ids: set = set()
    for raw_id in raw_ids:
        lookup_ids.add(raw_id)
        try:
            lookup_ids.add(ObjectId(raw_id) if isinstance(raw_id, str) else str(raw_id))
        except Exception:
            pass

    users_by_id: dict = {}
    if lookup_ids:
        async for user in collections.users.find(
            {"_id": {"$in": list(lookup_ids)}},
            {"nickname": 1, "email": 1, "role": 1},
        ):
            users_by_id[str(user["_id"])] = user

    unknown = {"nickname": "Usuario desconocido", "email": "N/A", "role": ""}
    results = []
    for doc in attempts:
        user = users_by_id.get(str(doc.get("user_id")))
        if user is None:
            logger.warning("Intento %s sin usuario asociado (user_id=%r)", doc.get("_id"), doc.get("user_id"))

        data = attempt_doc_to_response(doc.copy())
        data["user_info"] = {
            "nickname": user.get("nickname", unknown["nickname"]) if user else unknown["nickname"],
            "email": user.get("email", unknown["email"]) if user else unknown["email"],
            "role": user.get("role", unknown["role"]) if user else unknown["role"],
        }
        results.append(data)

    return results


@router.get("/attempts/my-attempts", response_model=List[ExamAttemptResponse])
async def list_my_attempts(
    current_user: dict = Depends(get_current_user)
):
    """
    Listar todos los intentos del usuario actual.
    """
    user_id = str(current_user.get("_id", ""))

    attempts = []
    async for doc in get_collections().exam_attempts.find(
        {"user_id": ObjectId(user_id)}
    ).sort("completed_at", -1):
        attempts.append(attempt_doc_to_response(doc))

    return attempts
