"""
Punto de entrada de la API.

Cambios respecto a la version anterior:

- `@app.on_event` (obsoleto) se sustituye por un `lifespan`, que ademas permite
  precargar el modelo y cerrar el cliente de MongoDB de forma ordenada.
- Los origenes CORS se leen del entorno; antes estaban escritos en el codigo, de
  modo que cambiar el dominio del frontend exigia un despliegue del backend.
- Se expone `X-Total-Count`. La cabecera se enviaba desde `/records`, pero sin
  `expose_headers` el navegador no puede leerla en peticiones cross-origin, asi
  que la paginacion del frontend siempre veia el total de la pagina actual.
- El montaje de `/uploads` ocurre al construir la aplicacion, no en el arranque:
  anadir rutas despues de que el servidor acepta peticiones no es fiable.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router as api_router
from app.core.logging import setup_logging
from app.core.settings import settings
from app.db.mongodb import close_client, create_indexes
from app.services.predictor import ensure_model_loaded

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando Medical Sign Recognition API (entorno=%s)", settings.environment)

    (settings.upload_dir / "documents").mkdir(parents=True, exist_ok=True)

    try:
        await create_indexes()
    except Exception:
        # Sin base de datos la API puede seguir sirviendo /health y /labels; el
        # fallo se registra pero no impide arrancar.
        logger.exception("No se pudieron crear los indices de MongoDB.")

    try:
        # Precargar evita que la primera prediccion del dia cargue TensorFlow.
        await ensure_model_loaded()
    except Exception:
        logger.exception("El modelo no pudo precargarse; /predict respondera 503 hasta resolverlo.")

    yield

    logger.info("Cerrando Medical Sign Recognition API")
    await close_client()


app = FastAPI(
    title="Medical Sign Recognition API",
    description="Backend de la plataforma de aprendizaje de lengua de senas medica.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Error interno del servidor",
                "path": request.url.path,
                "method": request.method,
            },
        )


app.include_router(api_router)

if settings.upload_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")


@app.get("/", tags=["Health Check"], summary="Estado del servicio")
async def read_root():
    return {
        "service": "Medical Sign Recognition API",
        "version": app.version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health Check"], summary="Health check")
async def health_check():
    return {"status": "ok"}
