"""Cycle de vie : renvoi en correction, dévalidation, archivage, date de remise future."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.interruptions import Interruption
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.interruption_statut import MotifRequest
from app.services import interruption_cycle_service as cycle

pytestmark = pytest.mark.asyncio


def _user(role_nom: str, user_id: int = 7) -> Utilisateur:
    role = Role()
    role.id = 1
    role.nom = role_nom
    role.role_permissions = []
    ur = UserRole()
    ur.scope_service_id = None
    ur.role = role
    user = Utilisateur()
    user.id = user_id
    user.login = role_nom.lower()
    user.user_roles = [ur]
    return user


def _interruption(statut: str, type_direction: str = "distribution") -> Interruption:
    i = Interruption()
    i.id = 42
    i.statut = statut
    i.type_direction = type_direction
    i.service_id = 3
    i.created_by_id = 1
    i.date_apparition = datetime(2026, 10, 1, 8, 0)
    i.date_remise = datetime(2026, 10, 1, 10, 0) if statut != "en_cours" else None
    i.duree_minutes = 120 if statut != "en_cours" else None
    i.validated_by_id = 9 if statut in ("valide", "archive") else None
    return i


@pytest.fixture
def db() -> AsyncMock:
    d = AsyncMock()
    d.flush = AsyncMock()
    return d


@pytest.fixture(autouse=True)
def _sans_effets_de_bord():
    with patch.object(cycle.repo, "ajouter", new_callable=AsyncMock) as ajouter, patch.object(
        cycle.repo, "supprimer_end", new_callable=AsyncMock
    ), patch.object(cycle, "log_audit", new_callable=AsyncMock), patch.object(
        cycle, "_region_id", new_callable=AsyncMock, return_value=None
    ), patch("app.services.notification_dispatch_service.schedule_event"), patch(
        "app.workers.tasks.indicateurs.recalcul_saifi_saidi_periode_task.delay"
    ):
        yield ajouter


async def test_motif_obligatoire() -> None:
    with pytest.raises(ValidationError):
        MotifRequest(motif="   ")


async def test_renvoi_reserve_admin_scr(db) -> None:
    with pytest.raises(HTTPException) as exc:
        await cycle.renvoyer_en_correction(db, _interruption("cloture"), "Feeder erroné", _user("SUPERVISEUR"))
    assert exc.value.status_code == 403


async def test_renvoi_remet_en_cours_et_trace_le_motif(db, _sans_effets_de_bord) -> None:
    it = _interruption("cloture")
    await cycle.renvoyer_en_correction(db, it, "Feeder erroné", _user("ADMIN_SCR"))
    assert it.statut == "en_cours"
    assert it.date_remise is None and it.duree_minutes is None
    kwargs = _sans_effets_de_bord.await_args.kwargs
    assert kwargs["action"] == "renvoi_correction"
    assert kwargs["ancien_statut"] == "cloture" and kwargs["motif"] == "Feeder erroné"
    db.commit.assert_awaited_once()


async def test_renvoi_refuse_si_validee(db) -> None:
    with pytest.raises(HTTPException) as exc:
        await cycle.renvoyer_en_correction(db, _interruption("valide"), "Erreur", _user("ADMIN_SCR"))
    assert exc.value.status_code == 422


async def test_devalidation_repasse_cloturee(db) -> None:
    it = _interruption("valide")
    await cycle.devalider(db, it, "Cause erronée", _user("ADMIN_SCR"))
    assert it.statut == "cloture"
    assert it.validated_by_id is None


async def test_devalidation_impossible_apres_archivage(db) -> None:
    with pytest.raises(HTTPException) as exc:
        await cycle.devalider(db, _interruption("archive"), "Cause erronée", _user("ADMIN_SCR"))
    assert exc.value.status_code == 422
    assert "archivée" in exc.value.detail["error"]


async def test_transport_corrige_par_admin_dispatching(db) -> None:
    it = _interruption("cloture", "transport")
    with pytest.raises(HTTPException):
        await cycle.renvoyer_en_correction(db, it, "Erreur de ligne", _user("ADMIN_SCR"))
    await cycle.renvoyer_en_correction(db, it, "Erreur de ligne", _user("ADMIN_DISPATCHING"))
    assert it.statut == "en_cours"


async def test_archivage_gele_les_validees_du_mois(db) -> None:
    a, b = _interruption("valide"), _interruption("valide")
    with patch.object(
        cycle.repo, "lister_validees_du_mois", new_callable=AsyncMock, return_value=[a, b]
    ), patch.object(cycle.repo, "compter_non_validees_du_mois", new_callable=AsyncMock, return_value=3):
        res = await cycle.archiver_mois(
            db, type_direction="distribution", annee=2026, mois=10, user=_user("ADMIN_SAQS")
        )
    assert (a.statut, b.statut) == ("archive", "archive")
    assert res.archivees == 2 and res.non_validees_restantes == 3


async def test_archivage_refuse_au_bcc(db) -> None:
    with pytest.raises(HTTPException) as exc:
        await cycle.archiver_mois(db, type_direction="distribution", annee=2026, mois=10, user=_user("BCC"))
    assert exc.value.status_code == 403


async def test_date_de_remise_future_refusee() -> None:
    from app.services.interruption_distribution_service import _ensure_remise_pas_dans_le_futur

    _ensure_remise_pas_dans_le_futur(datetime.utcnow() + timedelta(minutes=2))
    with pytest.raises(HTTPException) as exc:
        _ensure_remise_pas_dans_le_futur(datetime.utcnow() + timedelta(hours=2))
    assert exc.value.status_code == 422
