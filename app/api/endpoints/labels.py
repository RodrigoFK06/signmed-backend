from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from typing import List
import pandas as pd
import os
import logging
import unicodedata
from app.config import DATASET_PATH

router = APIRouter()
logger = logging.getLogger(__name__)

class LabelsResponse(BaseModel):
    labels: list[str]
    count: int

class LabelDetail(BaseModel):
    id: str
    name: str
    difficulty: str

class LabelsDetailResponse(BaseModel):
    labels: List[LabelDetail]
    count: int

def _normalize_label(s: str) -> str:
    """normaliza: trim, lower, quita acentos, deja [a-z0-9_], colapsa espacios->'_'"""
    s = (s or "").strip().lower()
    # quitar acentos
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    # reemplazar espacios por _
    s = "_".join(s.split())
    # filtrar caracteres no válidos
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789_"
    s = "".join(ch for ch in s if ch in allowed)
    return s

@router.get(
    "/labels",
    response_model=LabelsResponse,
    summary="Obtener etiquetas de señas",
    description="Retorna las señas médicas únicas (normalizadas) desde el dataset en el orden alfabético."
)
def get_labels(response: Response):
    # Evitar caché (el dataset puede cambiar)
    response.headers["Cache-Control"] = "no-store"

    dataset_path = str(DATASET_PATH)
    if not os.path.exists(dataset_path):
        logger.error("Dataset file not found at %s", dataset_path)
        # Devuelve vacío (200) para que el frontend no truene
        return LabelsResponse(labels=[], count=0)

    try:
        df = pd.read_csv(dataset_path, header=None)

        # Necesitamos al menos 2 columnas: penúltima = label
        if df.empty or df.shape[1] < 2:
            logger.error("El dataset está vacío o no tiene suficientes columnas.")
            return LabelsResponse(labels=[], count=0)

        label_col = df.columns[-2]  # penúltima columna (etiqueta)
        labels_series = df[label_col].dropna().astype(str)

        # Normalizar y filtrar vacíos
        labels_norm = labels_series.map(_normalize_label)
        labels_norm = labels_norm[labels_norm.str.len() > 0]

        # Únicas + ordenadas
        labels_unique = sorted(labels_norm.unique().tolist())

        return LabelsResponse(labels=labels_unique, count=len(labels_unique))

    except Exception as e:
        logger.exception("Error procesando el archivo del dataset.")
        raise HTTPException(status_code=500, detail=f"Error leyendo etiquetas: {str(e)}")


@router.get(
    "/labels/detailed",
    response_model=LabelsDetailResponse,
    summary="Obtener etiquetas con dificultad",
    description="Retorna las señas médicas con su nivel de dificultad"
)
def get_labels_detailed(response: Response):
    response.headers["Cache-Control"] = "no-store"
    
    dataset_path = str(DATASET_PATH)
    if not os.path.exists(dataset_path):
        logger.error("Dataset file not found at %s", dataset_path)
        return LabelsDetailResponse(labels=[], count=0)
    
    try:
        df = pd.read_csv(dataset_path, header=None)
        
        if df.empty or df.shape[1] < 3:
            logger.error("El dataset está vacío o no tiene suficientes columnas.")
            return LabelsDetailResponse(labels=[], count=0)
        
        # Columna -2 es el label, columna -1 es la dificultad
        df.columns = [*[f"col_{i}" for i in range(df.shape[1] - 2)], "label", "difficulty"]
        
        # Normalizar dificultad
        df["difficulty"] = df["difficulty"].astype(str).str.strip().str.lower()
        df["difficulty"] = df["difficulty"].replace({
            "principiante": "principiante",
            "intermedio": "intermedio",
            "avanzado": "avanzado"
        })
        
        # Normalizar labels
        df["label_norm"] = df["label"].astype(str).apply(_normalize_label)
        df = df[df["label_norm"].str.len() > 0]
        
        # Agrupar por label_norm y tomar el primer valor de dificultad
        df_unique = df.groupby("label_norm").agg({
            "label": "first",
            "difficulty": "first"
        }).reset_index()
        
        # Crear lista de LabelDetail
        labels_list = [
            LabelDetail(
                id=row["label_norm"],
                name=row["label"],
                difficulty=row["difficulty"] if row["difficulty"] in ["principiante", "intermedio", "avanzado"] else "principiante"
            )
            for _, row in df_unique.iterrows()
        ]
        
        # Ordenar alfabéticamente por id
        labels_list.sort(key=lambda x: x.id)
        
        return LabelsDetailResponse(labels=labels_list, count=len(labels_list))
    
    except Exception as e:
        logger.exception("Error procesando el archivo del dataset.")
        raise HTTPException(status_code=500, detail=f"Error leyendo etiquetas detalladas: {str(e)}")
