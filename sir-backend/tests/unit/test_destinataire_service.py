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
