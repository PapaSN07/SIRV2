"""Tests unitaires — envoi SMS manuel."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.notifications import Destinataire
from app.models.utilisateurs import Utilisateur
from app.services import manual_sms_service

pytestmark = pytest.mark.asyncio


def _user(telephone: str | None = "+221771234567") -> Utilisateur:
    u = Utilisateur()
    u.id = 5
    u.login = "bcc_user"
    u.nom = "Diop"
    u.prenom = "Amadou"
    u.email = "a@sn"
    u.telephone = telephone
    u.is_active = True
    u.user_roles = []
    return u


async def test_truncate_message_over_160() -> None:
    long_msg = "x" * 200
    assert len(manual_sms_service._truncate_message(long_msg)) == 160


async def test_send_manual_sms_requires_phone() -> None:
    dest = Destinataire()
    dest.id = 1
    dest.nom = "Sans tel"
    dest.telephone = None
    dest.is_active = True

    db = AsyncMock()
    admin = _user()

    with patch(
        "app.services.manual_sms_service.dest_repo.get_by_id",
        new=AsyncMock(return_value=dest),
    ), patch(
        "app.services.manual_sms_service.destinataire_service.assert_destinataire_in_scope",
        new=AsyncMock(),
    ):
        with pytest.raises(HTTPException) as exc:
            await manual_sms_service.send_manual_sms(
                db,
                admin,
                message="Hello",
                destinataire_ids=[1],
                utilisateur_ids=None,
            )
    assert exc.value.status_code == 422


async def test_send_manual_sms_un_seul_sms_par_numero() -> None:
    """Une personne cochée via deux groupes (deux fiches, même numéro) ne reçoit qu'un SMS."""
    from unittest.mock import MagicMock

    def dest(i: int, tel: str) -> Destinataire:
        d = Destinataire()
        d.id, d.nom, d.telephone, d.is_active = i, f"D{i}", tel, True
        return d

    fiches = {1: dest(1, "777408254"), 2: dest(2, "+221 77 740 82 54"), 3: dest(3, "781451126")}
    crees: list[dict] = []

    async def create_pending(db, **kw):
        crees.append(kw)
        return MagicMock(id=len(crees))

    celery = MagicMock()
    with patch(
        "app.services.manual_sms_service.dest_repo.get_by_id", new=AsyncMock(side_effect=lambda db, i: fiches[i])
    ), patch(
        "app.services.manual_sms_service.destinataire_service.assert_destinataire_in_scope", new=AsyncMock()
    ), patch("app.services.manual_sms_service.sms_repo.create_pending", new=create_pending), patch(
        "app.workers.celery_app.celery_app", celery
    ):
        rep = await manual_sms_service.send_manual_sms(
            AsyncMock(), _user(), message="Coupure", destinataire_ids=[1, 2, 3], utilisateur_ids=None
        )
    assert rep.sent_count == 2
    assert [c["destinataire_id"] for c in crees] == [1, 3]
    assert all(c["envoye_par_id"] == 5 for c in crees)
