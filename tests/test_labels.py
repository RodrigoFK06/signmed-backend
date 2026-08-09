"""
Tests del servicio de etiquetas.

Cubren la regresion principal: `/labels` debe resolverse sin tocar el dataset.
"""
from __future__ import annotations



import pytest

from app.services import labels as labels_service


@pytest.fixture(autouse=True)
def clean_cache():
    labels_service.reset_cache()
    yield
    labels_service.reset_cache()


def test_labels_no_leen_el_dataset(monkeypatch, tmp_path):
    """Abrir el CSV de entrenamiento al servir peticiones es un fallo, no un detalle."""
    import builtins

    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        if "dataset_medico" in str(file):
            raise AssertionError(f"El servicio de etiquetas no debe leer el dataset ({file}).")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr("pandas.read_csv", lambda *a, **k: pytest.fail("pandas no debe intervenir aqui."))

    assert labels_service.get_labels(), "Se esperaban etiquetas resueltas desde los artefactos."


def test_solo_se_exponen_clases_del_modelo():
    """Un metadato sin clase correspondiente no debe llegar a la API."""
    model_classes = set(labels_service._load_model_classes())
    served = {label.id for label in labels_service.get_labels()}
    assert served == model_classes


def test_las_etiquetas_obsoletas_no_se_ofrecen_para_practicar():
    practice = {label.id for label in labels_service.get_practice_labels()}
    deprecated = {label.id for label in labels_service.get_labels() if label.deprecated}

    assert deprecated, "El catalogo deberia marcar la clase duplicada del dataset."
    assert not (practice & deprecated)
    # Pero el modelo si puede emitirlas, asi que siguen siendo validas al predecir.
    assert deprecated <= labels_service.get_label_ids()


def test_agrupacion_por_dificultad_es_completa():
    grouped = labels_service.get_labels_by_difficulty()
    flat = [label for ids in grouped.values() for label in ids]

    assert set(grouped) == set(labels_service.DIFFICULTIES)
    assert sorted(flat) == sorted(label.id for label in labels_service.get_practice_labels())
    assert len(flat) == len(set(flat)), "Ninguna sena puede estar en dos niveles."


def test_clase_sin_metadatos_se_degrada_sin_romper(monkeypatch):
    """Sin catalogo, la API sigue sirviendo las clases del modelo."""
    monkeypatch.setattr(labels_service, "_load_catalog", dict)
    labels_service.reset_cache()

    served = labels_service.get_labels()
    assert served, "Sin catalogo se deben servir igualmente las clases del modelo."
    assert all(label.name for label in served), "Debe derivarse un nombre legible del id."
    assert all(label.difficulty == "beginner" for label in served)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("principiante", "beginner"),
        ("Intermedio", "intermediate"),
        ("  AVANZADO ", "advanced"),
        ("advanced", "advanced"),
        (None, "beginner"),
        ("desconocido", "beginner"),
    ],
)
def test_normalizacion_de_dificultad(raw, expected):
    assert labels_service.normalize_difficulty(raw) == expected
