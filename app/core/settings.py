"""
Configuracion central de la aplicacion.

Toda la configuracion se lee del entorno mediante pydantic-settings. Los valores
sensibles (SECRET_KEY, MONGO_URI) no tienen valor por defecto utilizable en
produccion: si faltan, la aplicacion falla al arrancar en lugar de operar con
credenciales conocidas publicamente.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Clave de desarrollo. Solo se acepta cuando ENVIRONMENT == "development".
DEV_SECRET_KEY = "dev-secret-do-not-use-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Entorno ---
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # --- Rutas de artefactos ---
    artifacts_dir: Path = BASE_DIR / "artifacts"
    data_dir: Path = BASE_DIR / "data"
    upload_dir: Path = BASE_DIR / "uploads"

    # --- Modelo ---
    model_filename: str = "lstm_holistic.h5"
    encoder_filename: str = "label_encoder.pkl"
    classes_filename: str = "classes.json"
    catalog_filename: str = "labels_catalog.json"

    sequence_frames: int = 35
    sequence_features: int = 150

    # El modelo publicado se entreno SIN estandarizar las features (ver
    # docs/MODEL_NOTES.md). Normalizar en inferencia introduce train/serve skew,
    # asi que por defecto se sirve tal y como se entreno. Cuando se reentrene
    # aplicando mean/std, basta con poner APPLY_FEATURE_NORMALIZATION=true.
    apply_feature_normalization: bool = False

    # Umbral de confianza (%) a partir del cual una prediccion se considera firme.
    confidence_threshold: float = Field(default=75.0, ge=0.0, le=100.0)

    # --- Seguridad ---
    secret_key: str = DEV_SECRET_KEY
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    min_password_length: int = Field(default=8, ge=8)

    # --- Base de datos ---
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "sign_language"

    # --- CORS ---
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Subidas ---
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Acepta una lista JSON o una cadena separada por comas."""
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [origin.strip().rstrip("/") for origin in stripped.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_dev_secret_outside_development(self) -> "Settings":
        if self.environment != "development" and self.secret_key == DEV_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY no esta configurada. Define una clave aleatoria "
                "(por ejemplo `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`) "
                f"antes de arrancar en entorno '{self.environment}'."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def model_path(self) -> Path:
        return self.artifacts_dir / self.model_filename

    @property
    def encoder_path(self) -> Path:
        return self.artifacts_dir / self.encoder_filename

    @property
    def classes_path(self) -> Path:
        return self.artifacts_dir / self.classes_filename

    @property
    def catalog_path(self) -> Path:
        return self.artifacts_dir / self.catalog_filename

    @property
    def dataset_path(self) -> Path:
        """Solo se usa en entrenamiento/analisis, nunca al servir peticiones."""
        return self.data_dir / "dataset_medico.csv"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
