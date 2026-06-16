"""Tests unitaires — service SMS mock."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import sms_service


@pytest.mark.asyncio
async def test_send_sms_record_mock_when_gateway_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(sms_service.settings, "sms_gateway_url", "")

    record = MagicMock()
    record.contenu = "Test SMS"
    destinataire = MagicMock()
    destinataire.telephone = "+221771234567"
    record.destinataire = destinataire

    db = AsyncMock()
    with patch(
        "app.services.sms_service.repo.get_by_id",
        new=AsyncMock(return_value=record),
    ), patch(
        "app.services.sms_service.repo.update_statut",
        new=AsyncMock(),
    ) as mock_update:
        result = await sms_service.send_sms_record(db, 1)

    assert result["statut"] == "envoye"
    mock_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_sms_record_echec_sans_telephone() -> None:
    record = MagicMock()
    record.destinataire = MagicMock(telephone=None)

    db = AsyncMock()
    with patch(
        "app.services.sms_service.repo.get_by_id",
        new=AsyncMock(return_value=record),
    ), patch(
        "app.services.sms_service.repo.update_statut",
        new=AsyncMock(),
    ) as mock_update:
        result = await sms_service.send_sms_record(db, 2)

    assert result["statut"] == "echec"
    mock_update.assert_awaited_once()
