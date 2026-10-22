"""Tests unitaires — statut_id / direction_source_id synchronisés, entreprise / prestataire."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.interruptions import Interruption, _sync_referentiel_ids
from app.models.referentiel import DIRECTION_SOURCE_IDS, STATUT_IDS
from app.services import interruption_distribution_service as svc

_GET_BY_ID = "app.services.interruption_distribution_service.ref_repo.get_by_id"


@pytest.mark.parametrize("statut", ["en_cours", "cloture", "valide", "archive"])
def test_sync_statut_id(statut: str) -> None:
    it = Interruption(type_direction="distribution", statut=statut)
    _sync_referentiel_ids(None, None, it)
    assert it.statut_id == STATUT_IDS[statut]


@pytest.mark.parametrize("direction", ["distribution", "transport", "omvg"])
def test_sync_direction_source_id(direction: str) -> None:
    it = Interruption(type_direction=direction, statut="en_cours")
    _sync_referentiel_ids(None, None, it)
    assert it.direction_source_id == DIRECTION_SOURCE_IDS[direction]


def test_sync_defaults_statut_en_cours() -> None:
    it = Interruption(type_direction="distribution")
    it.statut = None
    _sync_referentiel_ids(None, None, it)
    assert it.statut == "en_cours"
    assert it.statut_id == STATUT_IDS["en_cours"]


def test_sync_follows_statut_change() -> None:
    it = Interruption(type_direction="distribution", statut="en_cours")
    _sync_referentiel_ids(None, None, it)
    it.statut = "valide"
    _sync_referentiel_ids(None, None, it)
    assert it.statut_id == STATUT_IDS["valide"]


async def test_validate_intervenants_none_skips_lookup() -> None:
    with patch(_GET_BY_ID, AsyncMock()) as get_by_id:
        await svc._validate_intervenants(MagicMock(), entreprise_id=None, prestataire_id=None)
    get_by_id.assert_not_awaited()


async def test_validate_intervenants_ok() -> None:
    active = SimpleNamespace(is_active=True)
    with patch(_GET_BY_ID, AsyncMock(return_value=active)) as get_by_id:
        await svc._validate_intervenants(MagicMock(), entreprise_id=1, prestataire_id=2)
    assert get_by_id.await_count == 2


async def test_validate_intervenants_unknown_entreprise_422() -> None:
    with patch(_GET_BY_ID, AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc:
            await svc._validate_intervenants(MagicMock(), entreprise_id=99, prestataire_id=None)
    assert exc.value.status_code == 422
    assert "Entreprise" in exc.value.detail["error"]


async def test_validate_intervenants_inactive_prestataire_422() -> None:
    inactive = SimpleNamespace(is_active=False)
    with patch(_GET_BY_ID, AsyncMock(return_value=inactive)):
        with pytest.raises(HTTPException) as exc:
            await svc._validate_intervenants(MagicMock(), entreprise_id=None, prestataire_id=5)
    assert exc.value.status_code == 422
    assert "Prestataire" in exc.value.detail["error"]
