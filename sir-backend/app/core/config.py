import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent


def _resolve_env_files() -> tuple[str, ...]:
    """Charge les fichiers .env selon le profil SIR_PROFILE (docker | senelec).

    - docker (défaut) : .env racine + sir-backend/.env — base Docker locale
    - senelec         : .env.senelec — base SQL Server srv-bddomtech/SIRV2
    """
    profile = os.environ.get("SIR_PROFILE", "docker").strip().lower()
    paths: list[Path] = []

    if profile == "senelec":
        paths.extend(
            [
                _REPO_ROOT / ".env.senelec",
                _BACKEND_DIR / ".env.senelec",
            ]
        )
    else:
        paths.extend([_REPO_ROOT / ".env", _BACKEND_DIR / ".env"])

    resolved = tuple(str(p) for p in paths if p.is_file())
    return resolved or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis
    redis_url: str

    # JWT
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    # App
    environment: str = "development"
    api_version: str = "v1"
    cors_origins: str = Field(default="http://localhost:4200", validation_alias="CORS_ORIGINS")

    # SMS
    sms_gateway_url: str = ""
    sms_gateway_api_key: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Rapports (Sprint 6)
    rapports_storage_path: str = Field(
        default="./storage/rapports",
        validation_alias="RAPPORTS_STORAGE_PATH",
    )
    rapports_file_ttl_hours: int = Field(default=24, validation_alias="RAPPORTS_FILE_TTL_HOURS")

    # Seuil interruption fugitive (minutes)
    seuil_fugitif_minutes: int = Field(default=5, validation_alias="SEUIL_FUGITIF_MINUTES")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
