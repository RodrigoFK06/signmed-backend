"""
Catalogo de senas.

Version anterior: cada peticion a `/labels` y `/labels/detailed` hacia
`pd.read_csv()` sobre `data/dataset_medico.csv` (135 MB), con
`Cache-Control: no-store` para que el navegador nunca reutilizara la respuesta.
Cada carga de pagina reservaba cientos de MB y el contenedor moria por OOM;
cuando el CSV no estaba desplegado, el listado salia vacio sin error visible.

Ahora los datos vienen de `app.services.labels`, que los resuelve en memoria a
partir de las clases del modelo y un catalogo JSON de pocos kilobytes.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.services import labels as labels_service

router = APIRouter(tags=["Etiquetas"])

# El catalogo solo cambia al publicar un modelo nuevo, asi que se puede cachear.
_CACHE_CONTROL = "public, max-age=300"


class LabelsResponse(BaseModel):
    labels: List[str] = Field(..., description="Identificadores de las senas disponibles.")
    count: int


class LabelDetail(BaseModel):
    id: str = Field(..., examples=["tengo_fiebre_y_mareo"])
    name: str = Field(..., examples=["Tengo fiebre y mareo"])
    difficulty: str = Field(..., examples=["intermediate"])
    description: str = ""


class LabelsDetailResponse(BaseModel):
    labels: List[LabelDetail]
    count: int


@router.get(
    "/labels",
    response_model=LabelsResponse,
    summary="Listar las senas disponibles",
    description="Identificadores de las senas que el modelo publicado sabe reconocer, en orden alfabetico.",
)
async def get_labels(response: Response) -> LabelsResponse:
    response.headers["Cache-Control"] = _CACHE_CONTROL
    ids = [label.id for label in labels_service.get_practice_labels()]
    return LabelsResponse(labels=ids, count=len(ids))


@router.get(
    "/labels/detailed",
    response_model=LabelsDetailResponse,
    summary="Listar las senas con sus metadatos",
    description="Igual que /labels, anadiendo nombre legible, dificultad y descripcion.",
)
async def get_labels_detailed(response: Response) -> LabelsDetailResponse:
    response.headers["Cache-Control"] = _CACHE_CONTROL
    items = [
        LabelDetail(
            id=label.id,
            name=label.name,
            difficulty=label.difficulty,
            description=label.description,
        )
        for label in labels_service.get_practice_labels()
    ]
    return LabelsDetailResponse(labels=items, count=len(items))
