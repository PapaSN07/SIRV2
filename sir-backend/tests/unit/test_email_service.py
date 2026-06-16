"""Tests unitaires — service email mock."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services import email_service


@pytest.mark.asyncio
async def test_send_direct_mock_when_smtp_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(email_service.settings, "smtp_host", "")
    result = await email_service.send_direct(
        to_email="test@senelec.sn",
        sujet="[test] sujet",
        corps="<p>corps</p>",
    )
    assert result["statut"] == "envoye"


@pytest.mark.asyncio
async def test_send_direct_uses_smtp_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(email_service.settings, "smtp_host", "smtp.test.local")
    with patch("app.services.email_service.asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
        result = await email_service.send_direct(
            to_email="test@senelec.sn",
            sujet="sujet",
            corps="corps",
        )
    assert result["statut"] == "envoye"
    mock_thread.assert_awaited_once()
