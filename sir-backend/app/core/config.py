import os
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _BACKEND_DIR.parent

# Valeurs d'exemple publiées dans les fichiers .env.*.example : jamais acceptées hors tests.
_PLACEHOLDER_SECRET_PREFIX = "changeme"
_MIN_SECRET_KEY_LENGTH = 32


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

    # LDAP / Active Directory (compte de service bind)
    ldap_enabled: bool = Field(default=False, validation_alias="LDAP_ENABLED")
    ldap_hosts: str = Field(
        default="srv-siegedc0.electricite.sn,srv-siegedc2.electricite.sn,srv-datacentdc1.electricite.sn",
        validation_alias="LDAP_HOSTS",
    )
    ldap_port: int = Field(default=389, validation_alias="LDAP_PORT")
    ldap_use_ssl: bool = Field(default=False, validation_alias="LDAP_USE_SSL")
    ldap_bind_dn: str = Field(default="", validation_alias="LDAP_BIND_DN")
    ldap_bind_password: str = Field(default="", validation_alias="LDAP_BIND_PASSWORD")
    ldap_base_dn: str = Field(default="DC=electricite,DC=sn", validation_alias="LDAP_BASE_DN")
    ldap_user_search_filter: str = Field(
        default="(sAMAccountName={login})",
        validation_alias="LDAP_USER_SEARCH_FILTER",
    )
    ldap_timeout_seconds: int = Field(default=8, validation_alias="LDAP_TIMEOUT_SECONDS")

    @model_validator(mode="after")
    def _check_secret_key(self) -> "Settings":
        """Refuse de démarrer avec une clé JWT d'exemple ou trop courte.

        Avec une clé connue, n'importe qui peut signer un jeton valide pour
        n'importe quel compte. Seul l'environnement « test » y échappe.
        """
        if self.environment == "test":
            return self
        key = self.secret_key.strip()
        if key.lower().startswith(_PLACEHOLDER_SECRET_PREFIX) or len(key) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                "SECRET_KEY invalide : valeur d'exemple ou moins de "
                f"{_MIN_SECRET_KEY_LENGTH} caractères. Générer avec : openssl rand -hex 32"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ldap_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ldap_hosts.split(",") if host.strip()]

    @property
    def ldap_is_configured(self) -> bool:
        return bool(
            self.ldap_enabled
            and self.ldap_hosts_list
            and self.ldap_bind_dn.strip()
            and self.ldap_bind_password
        )


settings = Settings()
