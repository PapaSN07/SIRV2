"""Tests unitaires — service destinataires notifications."""

import pytest
from pydantic import ValidationError

from app.schemas.notifications import DestinataireCreate


def test_destinataire_create_requires_phone_or_email() -> None:
    with pytest.raises(ValidationError):
        DestinataireCreate(nom="Test", telephone=None, email=None)


def test_destinataire_create_accepts_phone_only() -> None:
    body = DestinataireCreate(nom="Test SMS", telephone="+221770000000")
    assert body.telephone == "+221770000000"
    assert body.email is None


def test_destinataire_create_accepts_email_only() -> None:
    body = DestinataireCreate(nom="Test Email", email="test@senelec.sn")
    assert body.email == "test@senelec.sn"


@pytest.mark.asyncio
async def test_update_groupe_envoi_libelle_deja_pris_409() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi import HTTPException

    from app.schemas.notifications import GroupeEnvoiUpdate
    from app.services import destinataire_service as svc

    groupe = MagicMock(id=1, libelle="DR DAKAR", exploitation="BCC", is_active=True)
    with patch.object(svc, "_ensure_can_admin"), patch.object(
        svc.repo, "get_groupe", new=AsyncMock(return_value=groupe)
    ), patch.object(svc.repo, "get_groupe_par_libelle", new=AsyncMock(return_value=MagicMock(id=2))):
        with pytest.raises(HTTPException) as exc:
            await svc.update_groupe_envoi(AsyncMock(), MagicMock(), 1, GroupeEnvoiUpdate(libelle="DIRECTION"))
    assert exc.value.status_code == 409
