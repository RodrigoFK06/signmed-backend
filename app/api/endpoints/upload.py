from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
import uuid

router = APIRouter()

# Directorio para almacenar documentos subidos
UPLOAD_DIR = Path("uploads/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint para subir documentos PDF de trabajadores de salud.
    Retorna la URL del archivo subido.
    """
    # Validar que sea un PDF
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    # Validar tamaño (máximo 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="El archivo es demasiado grande (máximo 10MB)")
    
    # Generar nombre único para el archivo
    file_extension = ".pdf"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Guardar el archivo
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
    
    # Retornar URL relativa
    file_url = f"/uploads/documents/{unique_filename}"
    
    return {
        "url": file_url,
        "filename": file.filename,
        "size": len(contents)
    }
