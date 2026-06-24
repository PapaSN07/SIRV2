"""Configuration migration — charge .env.migration puis profil SIR."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

MIGRATION_ROOT = Path(__file__).resolve().parent
REPO_ROOT = MIGRATION_ROOT.parents[1]


def _migration_env_files() -> tuple[str, ...]:
    paths = [
        REPO_ROOT / ".env.migration",
        MIGRATION_ROOT / ".env.migration",
    ]
    return tuple(str(p) for p in paths if p.is_file())


class MigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_migration_env_files() or (str(REPO_ROOT / ".env.migration"),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # HFSQL
    hfsql_driver: str = Field(default="HFSQL", validation_alias="HFSQL_DRIVER")
    hfsql_server: str = Field(default="srv-hfsql", validation_alias="HFSQL_SERVER")
    hfsql_port: int = Field(default=4900, validation_alias="HFSQL_PORT")
    hfsql_user: str = Field(default="admin", validation_alias="HFSQL_USER")
    hfsql_password: str = Field(default="", validation_alias="HFSQL_PASSWORD")
    hfsql_database: str = Field(default="SIR_ALHDL", validation_alias="HFSQL_DATABASE")
    hfsql_dsn: str = Field(default="", validation_alias="HFSQL_DSN")

    # Cible
    sir_profile: str = Field(default="senelec", validation_alias="SIR_PROFILE")
    database_url: str = Field(default="", validation_alias="DATABASE_URL")

    # Migration — fenêtre interruptions (prioritaire sur cutoff_years si date_from défini)
    migration_date_from: str = Field(default="2020-01-01", validation_alias="MIGRATION_DATE_FROM")
    migration_date_to: str = Field(default="2026-12-31", validation_alias="MIGRATION_DATE_TO")
    migration_cutoff_years: int = Field(default=3, validation_alias="MIGRATION_CUTOFF_YEARS")
    migration_dry_run: bool = Field(default=True, validation_alias="MIGRATION_DRY_RUN")
    migration_batch_size: int = Field(default=500, validation_alias="MIGRATION_BATCH_SIZE")
    migration_system_login: str = Field(
        default="migration.system", validation_alias="MIGRATION_SYSTEM_LOGIN"
    )
    migration_load_poste_interruptions: bool = Field(
        default=False, validation_alias="MIGRATION_LOAD_POSTE_INTERRUPTIONS"
    )

    @property
    def exports_dir(self) -> Path:
        return MIGRATION_ROOT / "exports"

    @property
    def reports_dir(self) -> Path:
        return MIGRATION_ROOT / "reports"

    @property
    def logs_dir(self) -> Path:
        return MIGRATION_ROOT / "logs"

    @property
    def id_maps_dir(self) -> Path:
        return MIGRATION_ROOT / "id_maps"

    @property
    def mapping_path(self) -> Path:
        return MIGRATION_ROOT / "mapping.yaml"


@lru_cache
def get_settings() -> MigrationSettings:
    os.environ.setdefault("SIR_PROFILE", "senelec")
    settings = MigrationSettings()
    if not settings.database_url:
        import scripts.migration._bootstrap  # noqa: F401, PLC0415 — env SIR_PROFILE

        from app.core.config import settings as app_settings

        object.__setattr__(settings, "database_url", app_settings.database_url)
    return settings


def ensure_dirs() -> None:
    s = get_settings()
    for d in (s.exports_dir, s.reports_dir, s.logs_dir, s.id_maps_dir):
        d.mkdir(parents=True, exist_ok=True)
