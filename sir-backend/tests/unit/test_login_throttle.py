"""Anti force brute sur /login et StartTLS LDAP."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis import aioredis
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.auth import LoginRequest
from app.services import auth_service, ldap_service, login_throttle_service as throttle


@pytest.fixture
async def redis():
    client = aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


async def test_blocage_apres_cinq_echecs(redis) -> None:
    for _ in range(throttle.MAX_FAILED_ATTEMPTS):
        await throttle.ensure_not_locked(redis, "Agent.BCC")
        await throttle.register_failure(redis, "agent.bcc")

    with pytest.raises(HTTPException) as exc:
        await throttle.ensure_not_locked(redis, "agent.bcc")
    assert exc.value.status_code == 429
    assert 0 < await redis.ttl("ratelimit:login:agent.bcc") <= throttle.WINDOW_SECONDS


async def test_succes_remet_le_compteur_a_zero(redis) -> None:
    await throttle.register_failure(redis, "agent")
    await throttle.reset(redis, "agent")
    await throttle.ensure_not_locked(redis, "agent")
    assert await redis.get("ratelimit:login:agent") is None


async def test_login_echoue_incremente_le_compteur(redis) -> None:
    with (
        patch("app.services.auth_service.utilisateur_repository.get_by_login", new_callable=AsyncMock, return_value=None),
        patch("app.services.auth_service.ldap_service.verify_user_password", return_value=None),
        pytest.raises(HTTPException),
    ):
        await auth_service.login(AsyncMock(), redis, LoginRequest(login="inconnu", password="x"))
    assert await redis.get("ratelimit:login:inconnu") == "1"


def test_start_tls_avant_le_bind() -> None:
    conn = MagicMock()
    conn.start_tls.return_value = True
    conn.bind.return_value = True
    with patch.object(settings, "ldap_start_tls", True), patch.object(settings, "ldap_use_ssl", False):
        assert ldap_service._bind(conn) is True
    conn.open.assert_called_once()
    conn.start_tls.assert_called_once()
    conn.bind.assert_called_once()


def test_start_tls_refuse_pas_de_bind() -> None:
    conn = MagicMock()
    conn.start_tls.return_value = False
    with patch.object(settings, "ldap_start_tls", True), patch.object(settings, "ldap_use_ssl", False):
        assert ldap_service._bind(conn) is False
    conn.bind.assert_not_called()
