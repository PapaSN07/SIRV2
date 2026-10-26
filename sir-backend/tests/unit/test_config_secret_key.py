"""Garde-fou SECRET_KEY : l'application refuse une clé d'exemple ou trop courte."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_BASE = {
    "database_url": "mssql+aioodbc://u:p@localhost/db",
    "redis_url": "redis://localhost:6379/0",
    "celery_broker_url": "redis://localhost:6379/1",
    "celery_result_backend": "redis://localhost:6379/2",
}


def _settings(secret_key: str, environment: str) -> Settings:
    return Settings(_env_file=None, secret_key=secret_key, environment=environment, **_BASE)


@pytest.mark.parametrize("environment", ["development", "production"])
def test_placeholder_secret_key_is_refused(environment: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY invalide"):
        _settings("changeme_generate_with_openssl_rand_hex_32", environment)


def test_short_secret_key_is_refused() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY invalide"):
        _settings("trop-courte", "production")


def test_strong_secret_key_is_accepted() -> None:
    settings = _settings("a" * 64, "production")
    assert settings.secret_key == "a" * 64


def test_test_environment_is_exempt() -> None:
    settings = _settings("cle_de_test", "test")
    assert settings.environment == "test"
