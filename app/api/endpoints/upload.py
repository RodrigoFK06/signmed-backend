"""
Subida de la documentacion acreditativa del personal de salud.

Es un endpoint deliberadamente anonimo: el usuario adjunta su titulacion durante
el registro, antes de tener cuenta. Por eso se refuerzan las validaciones:

- El tamano se controla **mientras** se lee. La version anterior hacia
  `await file.read()` y comprobaba la longitud despues, asi que una subida de
  varios GB agotaba la memoria del proceso antes de llegar al `if`.
- Se comprueba la cabecera del fichero, no solo que el nombre acabe en `.pdf`.
- El nombre en disco es un UUID; nunca se usa el que envia el cliente.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Uploads"])

PDF_MAGIC = b"%PDF-"
CHUNK_SIZE = 64 * 1024


def _documents_dir() -> Path:
    path = settings.upload_dir / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/upload-document", summary="Subir el documento acreditativo (PDF)")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF.",
        )

    destination = _documents_dir() / f"{uuid.uuid4()}.pdf"
    total = 0

    try:
        with destination.open("wb") as buffer:
            first_chunk = True
            while chunk := await file.read(CHUNK_SIZE):
                if first_chunk:
                    if not chunk.startswith(PDF_MAGIC):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El archivo no es un PDF valido.",
                        )
                    first_chunk = False

                total += len(chunk)
                if total > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"El archivo supera el maximo de {settings.max_upload_bytes // (1024 * 1024)} MB.",
                    )
                buffer.write(chunk)

        if total == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo esta vacio.",
            )
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except OSError:
        destination.unlink(missing_ok=True)
        logger.exception("No se pudo guardar el documento subido.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el documento.",
        )

    logger.info("Documento acreditativo guardado (%d bytes) como %s", total, destination.name)
    return {"url": f"/uploads/documents/{destination.name}", "size": total}
