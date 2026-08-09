"""
Servicio de etiquetas.

La fuente de verdad de las clases es el `LabelEncoder` con el que se entreno el
modelo: solo esas etiquetas pueden salir de una prediccion. Los metadatos de
presentacion (nombre legible, dificultad, descripcion) viven en
`artifacts/labels_catalog.json`.

Antes esta informacion se derivaba leyendo `data/dataset_medico.csv` (135 MB)
con pandas en cada peticion a `/labels`, `/labels/detailed` y
`/progress/level-progress`. Ademas de agotar la memoria del contenedor, ataba la
API a un fichero que no se versiona, de modo que en produccion el listado
quedaba vacio. Ahora todo se resuelve en memoria a partir de artefactos de unos
pocos kilobytes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Literal, Optional

from app.core.settings import settings

logger = logging.getLogger(__name__)

Difficulty = Literal["beginner", "intermediate", "advanced"]
DIFFICULTIES: tuple[Difficulty, ...] = ("beginner", "intermediate", "advanced")

# El dataset guarda la dificultad en castellano; el resto del sistema (examenes,
# frontend) usa las claves en ingles.
_DIFFICULTY_ALIASES: Dict[str, Difficulty] = {
    "principiante": "beginner",
    "intermedio": "intermediate",
    "avanzado": "advanced",
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}


@dataclass(frozen=True)
class Label:
    id: str
    name: str
    difficulty: Difficulty
    description: str = ""
    # Clase que el modelo sabe emitir pero que no debe ofrecerse para practicar
    # (p. ej. una etiqueta duplicada por un error tipografico en el dataset).
    deprecated: bool = False


def normalize_difficulty(value: Optional[str]) -> Difficulty:
    return _DIFFICULTY_ALIASES.get((value or "").strip().lower(), "beginner")


def _humanize(label_id: str) -> str:
    return label_id.replace("_", " ").strip().capitalize()


def _load_catalog() -> Dict[str, Label]:
    """Lee los metadatos de presentacion. Si faltan, se degrada con elegancia."""
    path = settings.catalog_path
    if not path.exists():
        logger.warning("Catalogo de etiquetas no encontrado en %s; se usaran nombres derivados del id.", path)
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("No se pudo leer el catalogo de etiquetas en %s", path)
        return {}

    catalog: Dict[str, Label] = {}
    for entry in raw.get("labels", []):
        label_id = str(entry.get("id", "")).strip().lower()
        if not label_id:
            continue
        catalog[label_id] = Label(
            id=label_id,
            name=entry.get("name") or _humanize(label_id),
            difficulty=normalize_difficulty(entry.get("difficulty")),
            description=entry.get("description", ""),
            deprecated=bool(entry.get("deprecated", False)),
        )
    return catalog


def _load_model_classes() -> List[str]:
    """
    Clases que el modelo publicado sabe predecir, en el orden del encoder.

    Se prefiere `classes.json` porque es texto plano y no requiere deserializar
    un pickle de scikit-learn; el encoder queda como respaldo.
    """
    classes_path = settings.classes_path
    if classes_path.exists():
        try:
            classes = json.loads(classes_path.read_text(encoding="utf-8"))
            if isinstance(classes, list) and classes:
                return [str(c).strip().lower() for c in classes]
        except (OSError, json.JSONDecodeError):
            logger.exception("No se pudo leer %s; se intentara con el encoder.", classes_path)

    encoder_path = settings.encoder_path
    if not encoder_path.exists():
        logger.error("No hay artefactos de clases disponibles (%s ni %s).", classes_path, encoder_path)
        return []

    try:
        import joblib  # import local: solo necesario en el camino de respaldo

        encoder = joblib.load(str(encoder_path))
        return [str(c).strip().lower() for c in getattr(encoder, "classes_", [])]
    except Exception:
        logger.exception("No se pudo cargar el encoder desde %s", encoder_path)
        return []


@lru_cache(maxsize=1)
def get_labels() -> List[Label]:
    """
    Etiquetas servibles, ordenadas alfabeticamente.

    Solo se exponen clases que el modelo puede predecir. Una entrada del
    catalogo sin clase correspondiente se ignora (metadato huerfano) y una clase
    sin entrada en el catalogo se sirve con valores derivados del id, para que
    anadir una sena al modelo nunca rompa la API.
    """
    catalog = _load_catalog()
    model_classes = _load_model_classes()

    if not model_classes:
        logger.error("El modelo no expone clases; /labels devolvera una lista vacia.")
        return []

    orphan_metadata = sorted(set(catalog) - set(model_classes))
    if orphan_metadata:
        logger.warning("Entradas del catalogo sin clase en el modelo (ignoradas): %s", orphan_metadata)

    missing_metadata = sorted(set(model_classes) - set(catalog))
    if missing_metadata:
        logger.warning("Clases del modelo sin metadatos en el catalogo: %s", missing_metadata)

    labels = [
        catalog.get(class_id, Label(id=class_id, name=_humanize(class_id), difficulty="beginner"))
        for class_id in model_classes
    ]
    return sorted(labels, key=lambda label: label.id)


@lru_cache(maxsize=1)
def get_practice_labels() -> List[Label]:
    """Etiquetas que se ofrecen al usuario para practicar y evaluar."""
    return [label for label in get_labels() if not label.deprecated]


@lru_cache(maxsize=1)
def get_label_ids() -> frozenset[str]:
    """Todas las clases que el modelo puede emitir, incluidas las obsoletas."""
    return frozenset(label.id for label in get_labels())


@lru_cache(maxsize=1)
def get_labels_by_difficulty() -> Dict[Difficulty, List[str]]:
    grouped: Dict[Difficulty, List[str]] = {difficulty: [] for difficulty in DIFFICULTIES}
    for label in get_practice_labels():
        grouped[label.difficulty].append(label.id)
    return grouped


def is_valid_label(label_id: Optional[str]) -> bool:
    if not label_id:
        return False
    return label_id.strip().lower() in get_label_ids()


def reset_cache() -> None:
    """Invalida las caches. Util en tests y tras publicar un modelo nuevo."""
    get_labels.cache_clear()
    get_practice_labels.cache_clear()
    get_label_ids.cache_clear()
    get_labels_by_difficulty.cache_clear()
