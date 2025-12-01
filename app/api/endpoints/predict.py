import traceback
from fastapi import APIRouter, HTTPException, Response, Depends

from app.models.schema import PredictRequest
from app.services.predictor import predict_sequence

# ⬇️ Importa el usuario autenticado desde tu servicio de auth
# Debe devolver dict con al menos { "nickname": "...", "email": "...", "role": "..." }
try:
    from app.services.auth import get_current_user  # JWT -> dict
except Exception as _:
    # Fallback para entornos sin auth (no recomendado en prod)
    def get_current_user():
        return {"nickname": None, "email": None, "role": "ANON"}

router = APIRouter()

@router.post(
    "/predict_raw",                 # mantenemos tu ruta temporal
    response_model=None,            # sin validación estricta de salida
    summary="Predict a medical sign from a sequence of keypoints",
    description="Recibe 35x150 (o 35x42 legacy) y retorna label + confidence(0-100) + probabilities."
)
async def predict(request: PredictRequest, response: Response, current_user: dict = Depends(get_current_user)):
    try:
        response.headers["Cache-Control"] = "no-store"

        auth_nickname = (current_user or {}).get("nickname") or (current_user or {}).get("email")
        user_id = str((current_user or {}).get("_id", ""))  # Obtener el ID del usuario

        print("🔥 predict_raw(): usando endpoint de app/api/endpoints/predict.py")
        print(
            "📩 Entrada recibida (shapes):",
            f"frames={len(request.sequence)}",
            f"features={len(request.sequence[0]) if request.sequence and request.sequence[0] else 'n/a'}",
            f"expected_label={request.expected_label}",
            f"auth_nickname={auth_nickname}",
            f"user_id={user_id}",
        )

        # Pasar el nickname y user_id autenticado al servicio
        raw = await predict_sequence(request, auth_nickname=auth_nickname, user_id=user_id)
        return raw

    except HTTPException:
        raise
    except ValueError as e:
        print("⚠️ ValueError en predict():", str(e))
        raise HTTPException(status_code=422, detail={"error": "VALUE_ERROR", "message": str(e)})
    except Exception as e:
        print("❌ Excepción en predict():", str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error interno en la predicción: {str(e)}")
