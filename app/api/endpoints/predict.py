"""Endpoint de inferencia."""
import logging

from fastapi import APIRouter, Depends, Response

from app.models.schema import BackendPredictResponse, PredictRequest
from app.services.auth import get_current_user
from app.services.predictor import predict_sequence

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Prediccion"])


@router.post(
    "/predict",
    response_model=BackendPredictResponse,
    summary="Reconocer una sena medica a partir de una secuencia de keypoints",
    description=(
        "Recibe una secuencia de 35 frames x 150 features y devuelve la etiqueta "
        "predicha, la confianza (0-100) y el vector de probabilidades."
    ),
)
async def predict(
    request: PredictRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """
    Requiere sesion.

    La version anterior envolvia el import de `get_current_user` en un
    `try/except` que, si fallaba, definia un usuario anonimo. Esa red de
    seguridad convertia cualquier error de importacion en un endpoint publico
    que ademas escribia registros sin dueno.
    """
    response.headers["Cache-Control"] = "no-store"

    nickname = current_user.get("nickname") or current_user.get("email")
    user_id = str(current_user.get("_id", ""))

    logger.debug(
        "Prediccion solicitada por %s (frames=%d, esperado=%s)",
        user_id, len(request.sequence), request.expected_label,
    )

    return await predict_sequence(request, auth_nickname=nickname, user_id=user_id)
