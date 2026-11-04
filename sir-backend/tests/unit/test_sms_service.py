"""Tests unitaires — service SMS mock."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import sms_service


@pytest.mark.asyncio
async def test_send_sms_record_echec_quand_passerelle_non_configuree(monkeypatch) -> None:
    """Sans passerelle, le SMS n'est jamais marqué « envoyé » (il n'a pas quitté SIRV2)."""
    monkeypatch.setattr(sms_service.settings, "sms_gateway_url", "")
    monkeypatch.setattr(sms_service.settings, "sms_gateway_wsdl", "")

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

    assert result["statut"] == "echec"
    mock_update.assert_awaited_once()
    assert mock_update.await_args.kwargs["statut"] == "echec"
    assert "non configurée" in mock_update.await_args.kwargs["erreur"]


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
