"""Tests unitaires — service interruption distribution (phase 3.1)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.reseau import Feeder, SousFeeder, Poste
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.interruption_distribution import (
    InterruptionDistributionCreate,
    InterruptionDistributionUpdate,
    PosteInterruptionCreate,
)
from app.schemas.common import PaginatedResponse
from app.services import interruption_distribution_service as svc

pytestmark = pytest.mark.asyncio


def _make_bcc(scope_service_id: int = 1) -> Utilisateur:
    role = Role()
    role.id = 1
    role.nom = "BCC"
    role.role_permissions = []
    ur = UserRole()
    ur.scope_service_id = scope_service_id
    ur.role = role
    user = Utilisateur()
    user.id = 1
    user.user_roles = [ur]
    return user


def _active_cause() -> Cause:
    c = Cause()
    c.id = 1
    c.is_active = True
    c.type_reseau = "distribution"
    return c


def _active_nature() -> Nature:
    n = Nature()
    n.id = 1
    n.is_active = True
    return n


def _active_siege() -> Siege:
    s = Siege()
    s.id = 1
    s.is_active = True
    s.type_reseau = "distribution"
    return s


def _active_signalisation() -> Signalisation:
    s = Signalisation()
    s.id = 1
    s.is_active = True
    s.type_reseau = "distribution"
    return s


def _feeder(service_id: int, feeder_id: int = 1) -> Feeder:
    f = Feeder()
    f.id = feeder_id
    f.service_id = service_id
    f.poste_source_id = 10
    f.is_active = True
    return f


def _sous_feeder(feeder_id: int = 1, sous_feeder_id: int = 1) -> SousFeeder:
    sf = SousFeeder()
    sf.id = sous_feeder_id
    sf.feeder_id = feeder_id
    sf.is_active = True
    return sf


def _create_body() -> InterruptionDistributionCreate:
    return InterruptionDistributionCreate(
        date_apparition=datetime(2026, 6, 12, 10, 30, 0),
        poste_source_id=10,
        feeder_id=1,
        sous_feeder_id=1,
        cause_id=1,
        nature_id=1,
        siege_id=1,
        signalisation_id=1,
        type_end_id=1,
        type_reseau_id=1,
    )


def _make_brc(scope_region_id: int = 3) -> Utilisateur:
    role = Role()
    role.id = 2
    role.nom = "BRC"
    role.role_permissions = []
    ur = UserRole()
    ur.scope_service_id = scope_region_id
    ur.role = role
    user = Utilisateur()
    user.id = 2
    user.user_roles = [ur]
    return user


async def test_create_bcc_wrong_service_raises_403() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)

    with patch(
        "app.services.interruption_distribution_service.reseau_repo.get_feeder",
        new_callable=AsyncMock,
        return_value=_feeder(service_id=2),
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_sous_feeder",
        new_callable=AsyncMock,
        return_value=_sous_feeder(),
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.create(db, _create_body(), user)

    assert exc.value.status_code == 403


async def test_create_brc_service_outside_region_raises_403() -> None:
    db = AsyncMock()
    user = _make_brc(scope_region_id=3)

    with patch(
        "app.services.interruption_distribution_service.reseau_repo.get_feeder",
        new_callable=AsyncMock,
        return_value=_feeder(service_id=99),
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_sous_feeder",
        new_callable=AsyncMock,
        return_value=_sous_feeder(),
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.create(db, _create_body(), user)

    assert exc.value.status_code == 403


async def test_create_brc_service_in_region_passes_scope() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_brc(scope_region_id=3)
    now = datetime(2026, 6, 12, 10, 30, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    interruption.statut = "en_cours"
    interruption.service_id = 5
    interruption.feeder_id = 1
    interruption.poste_source_id = 10
    interruption.date_apparition = now
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_by_id = 2
    interruption.created_at = now
    interruption.updated_at = now

    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False
    interruption.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_feeder",
        new_callable=AsyncMock,
        return_value=_feeder(service_id=5),
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_sous_feeder",
        new_callable=AsyncMock,
        return_value=_sous_feeder(),
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.interruption_distribution_service.ref_repo.get_by_id",
        new_callable=AsyncMock,
        side_effect=[
            _active_cause(),
            _active_nature(),
            _active_siege(),
            _active_signalisation(),
            _active_signalisation(),
            _active_signalisation(),
        ],
    ), patch(
        "app.services.interruption_distribution_service.repo.next_numero_interruption",
        new_callable=AsyncMock,
        return_value=1,
    ), patch(
        "app.services.interruption_distribution_service.repo.create_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(interruption, distribution),
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ):
        result = await svc.create(db, _create_body(), user)

    assert result.statut == "en_cours"
    assert result.service_id == 5
    db.commit.assert_awaited_once()


async def test_create_poste_source_mismatch_raises_422() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    body = _create_body().model_copy(update={"poste_source_id": 99})

    with patch(
        "app.services.interruption_distribution_service.reseau_repo.get_feeder",
        new_callable=AsyncMock,
        return_value=_feeder(service_id=1),
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.create(db, body, user)

    assert exc.value.status_code == 422


async def test_create_success_returns_en_cours() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    now = datetime(2026, 6, 12, 10, 30, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.numero_interruption = 5
    interruption.type_direction = "distribution"
    interruption.statut = "en_cours"
    interruption.service_id = 1
    interruption.feeder_id = 1
    interruption.poste_source_id = 10
    interruption.date_apparition = now
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_by_id = 1
    interruption.created_at = now
    interruption.updated_at = now

    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False
    interruption.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_feeder",
        new_callable=AsyncMock,
        return_value=_feeder(service_id=1),
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_sous_feeder",
        new_callable=AsyncMock,
        return_value=_sous_feeder(),
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "app.services.interruption_distribution_service.ref_repo.get_by_id",
        new_callable=AsyncMock,
        side_effect=[
            _active_cause(),
            _active_nature(),
            _active_siege(),
            _active_signalisation(),
            _active_signalisation(),
            _active_signalisation(),
        ],
    ), patch(
        "app.services.interruption_distribution_service.repo.next_numero_interruption",
        new_callable=AsyncMock,
        return_value=5,
    ), patch(
        "app.services.interruption_distribution_service.repo.create_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(interruption, distribution),
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ):
        result = await svc.create(db, _create_body(), user)

    assert result.statut == "en_cours"
    assert result.numero_interruption == 5
    db.commit.assert_awaited_once()


async def test_list_items_bcc_scope_passed_to_repository() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=3)
    now = datetime(2026, 6, 12, 10, 30, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    interruption.statut = "en_cours"
    interruption.service_id = 3
    interruption.feeder_id = 1
    interruption.poste_source_id = 1
    interruption.date_apparition = now
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_by_id = 1
    interruption.created_at = now
    interruption.updated_at = now
    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False
    distribution.is_programme = False
    distribution.has_extension_bt = False
    interruption.interruption_distribution = distribution

    paginated = PaginatedResponse(items=[interruption], total=1, page=1, page_size=20)

    with patch(
        "app.services.interruption_distribution_service.repo.list_interruptions_paginated",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        result = await svc.list_items(db, user, page=1, page_size=20)

    assert result.total == 1
    assert result.items[0].service_id == 3
    mock_list.assert_awaited_once()
    assert mock_list.await_args.kwargs["scope"].region_id == 3


async def test_get_item_wrong_service_raises_403() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 2
    interruption.type_direction = "distribution"
    interruption.interruption_distribution = InterruptionDistribution()

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_detail",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.service_in_region",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.get_item(db, 1, user)

    assert exc.value.status_code == 403


async def test_get_item_not_found_raises_404() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_detail",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.get_item(db, 999, user)

    assert exc.value.status_code == 404


async def test_add_poste_cloture_raises_422() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.feeder_id = 1
    interruption.statut = "cloture"
    interruption.type_direction = "distribution"

    with patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.add_poste(db, 1, PosteInterruptionCreate(poste_id=1), user)

    assert exc.value.status_code == 422


async def test_add_poste_success() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.feeder_id = 1
    interruption.statut = "en_cours"

    poste = Poste()
    poste.id = 1
    poste.code = "PT-01"
    poste.libelle = "Poste test"
    poste.service_id = 1
    poste.feeder_id = 1
    poste.is_active = True

    link = PosteInterruption()
    link.id = 10
    link.poste_id = 1
    link.nombre_clients_touches = 20
    link.poste = poste

    with patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.reseau_repo.get_poste",
        new_callable=AsyncMock,
        return_value=poste,
    ), patch(
        "app.services.interruption_distribution_service.repo.get_poste_interruption_link",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.services.interruption_distribution_service.repo.add_poste_interruption",
        new_callable=AsyncMock,
        return_value=link,
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ):
        result = await svc.add_poste(
            db, 1, PosteInterruptionCreate(poste_id=1, nombre_clients_touches=20), user
        )

    assert result.poste_code == "PT-01"
    db.commit.assert_awaited_once()


async def test_update_creator_success() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 1
    now = datetime(2026, 6, 12, 10, 30, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"
    interruption.created_by_id = 1
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.date_apparition = now
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_at = now
    interruption.updated_at = now
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False
    distribution.is_programme = False
    distribution.has_extension_bt = False
    interruption.interruption_distribution = distribution

    updated = Interruption()
    updated.id = 1
    updated.numero_interruption = 1
    updated.type_direction = "distribution"
    updated.statut = "en_cours"
    updated.service_id = 1
    updated.feeder_id = 1
    updated.poste_source_id = 1
    updated.date_apparition = now
    updated.cause_id = 1
    updated.nature_id = 1
    updated.siege_id = 1
    updated.signalisation_id = 1
    updated.observations = "Modifié"
    updated.is_force_majeure = False
    updated.is_fugitive = False
    updated.created_by_id = 1
    updated.created_at = now
    updated.updated_at = now
    updated.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=updated,
    ), patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.update_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(updated, distribution),
    ) as mock_update, patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ) as mock_audit:
        result = await svc.update(
            db, 1, InterruptionDistributionUpdate(observations="Modifié"), user
        )

    assert result.observations == "Modifié"
    assert mock_update.await_args.kwargs["interruption_updates"]["updated_by_id"] == user.id
    mock_audit.assert_awaited_once()
    db.commit.assert_awaited_once()


async def test_update_other_bcc_raises_403() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 99

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"
    interruption.created_by_id = 1
    interruption.interruption_distribution = InterruptionDistribution()

    with patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.update(
                db, 1, InterruptionDistributionUpdate(observations="Hack"), user
            )

    assert exc.value.status_code == 403


async def test_cloturer_success_enqueues_celery() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 1
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 30, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"
    interruption.created_by_id = 1
    interruption.date_apparition = apparition
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_at = apparition
    interruption.updated_at = apparition
    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False
    distribution.is_programme = False
    distribution.has_extension_bt = False

    closed = Interruption()
    closed.id = 1
    closed.numero_interruption = 1
    closed.type_direction = "distribution"
    closed.statut = "cloture"
    closed.service_id = 1
    closed.feeder_id = 1
    closed.poste_source_id = 1
    closed.date_apparition = apparition
    closed.date_remise = remise
    closed.duree_minutes = 150
    closed.cause_id = 1
    closed.nature_id = 1
    closed.siege_id = 1
    closed.signalisation_id = 1
    closed.is_force_majeure = False
    closed.is_fugitive = False
    closed.created_by_id = 1
    closed.created_at = apparition
    closed.updated_at = remise
    closed.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=closed,
    ), patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.count_postes_for_interruption",
        new_callable=AsyncMock,
        return_value=1,
    ), patch(
        "app.services.interruption_distribution_service.repo.update_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(closed, distribution),
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ), patch("app.workers.tasks.indicateurs.calcul_end_task.delay") as delay_mock:
        from app.schemas.interruption_distribution import InterruptionClotureRequest

        result = await svc.cloturer(
            db, 1, InterruptionClotureRequest(date_remise=remise), user
        )

    assert result.statut == "cloture"
    assert result.duree_minutes == 150
    delay_mock.assert_called_once_with(1)
    db.commit.assert_awaited_once()


async def test_cloturer_no_postes_raises_422() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 1

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"
    interruption.created_by_id = 1
    interruption.date_apparition = datetime(2026, 6, 12, 10, 0, 0)

    with patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.count_postes_for_interruption",
        new_callable=AsyncMock,
        return_value=0,
    ):
        from app.schemas.interruption_distribution import InterruptionClotureRequest

        with pytest.raises(HTTPException) as exc:
            await svc.cloturer(
                db,
                1,
                InterruptionClotureRequest(date_remise=datetime(2026, 6, 12, 12, 0, 0)),
                user,
            )

    assert exc.value.status_code == 422
    assert "plus de 5 minutes" in exc.value.detail["error"]


async def test_cloturer_cinq_minutes_sans_poste_passe() -> None:
    """5 minutes ou moins : la clôture n'exige pas de poste impacté."""
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 1
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 10, 4, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"
    interruption.created_by_id = 1
    interruption.date_apparition = apparition
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    interruption.is_force_majeure = False
    interruption.is_fugitive = True
    interruption.created_at = apparition
    interruption.updated_at = apparition
    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False

    closed = Interruption()
    closed.id = 1
    closed.numero_interruption = 1
    closed.type_direction = "distribution"
    closed.statut = "cloture"
    closed.service_id = 1
    closed.date_apparition = apparition
    closed.date_remise = remise
    closed.duree_minutes = 4
    closed.is_force_majeure = False
    closed.is_fugitive = True
    closed.created_by_id = 1
    closed.created_at = apparition
    closed.updated_at = remise
    closed.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=closed,
    ), patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.count_postes_for_interruption",
        new_callable=AsyncMock,
        return_value=0,
    ) as count_postes, patch(
        "app.services.interruption_distribution_service.repo.update_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(closed, distribution),
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ), patch("app.workers.tasks.indicateurs.calcul_end_task.delay"):
        from app.schemas.interruption_distribution import InterruptionClotureRequest

        result = await svc.cloturer(
            db, 1, InterruptionClotureRequest(date_remise=remise), user
        )

    assert result.statut == "cloture"
    assert result.duree_minutes == 4
    count_postes.assert_not_awaited()


async def test_cloturer_date_avec_fuseau_ne_plante_pas() -> None:
    from datetime import timezone

    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 10, 3, 0, tzinfo=timezone.utc)
    assert svc._compute_duree_minutes(apparition, remise) == 3


async def test_valider_success_enqueues_saifi_saidi() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.id = 10
    user.user_roles[0].role.nom = "SUPERVISEUR"

    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 0, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "cloture"
    interruption.date_apparition = apparition
    interruption.date_remise = remise
    interruption.duree_minutes = 120
    interruption.validated_by_id = None
    interruption.numero_interruption = 1
    interruption.type_direction = "distribution"
    interruption.created_by_id = 1
    interruption.created_at = apparition
    interruption.updated_at = apparition
    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False

    validated = Interruption()
    validated.id = 1
    validated.numero_interruption = 1
    validated.type_direction = "distribution"
    validated.statut = "valide"
    validated.service_id = 1
    validated.feeder_id = 1
    validated.poste_source_id = 1
    validated.date_apparition = apparition
    validated.date_remise = remise
    validated.duree_minutes = 120
    validated.validated_by_id = 10
    validated.cause_id = 1
    validated.nature_id = 1
    validated.siege_id = 1
    validated.signalisation_id = 1
    validated.is_force_majeure = False
    validated.is_fugitive = False
    validated.created_by_id = 1
    validated.created_at = apparition
    validated.updated_at = remise
    validated.interruption_distribution = distribution

    with patch(
        "app.services.interruption_distribution_service.repo.get_interruption_for_response",
        new_callable=AsyncMock,
        return_value=validated,
    ), patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.interruption_distribution_service.repo.update_interruption_distribution",
        new_callable=AsyncMock,
        return_value=(validated, distribution),
    ), patch(
        "app.services.interruption_distribution_service.log_audit",
        new_callable=AsyncMock,
    ), patch(
        "app.services.interruption_distribution_service.end_repo.get_region_id_for_service",
        new_callable=AsyncMock,
        return_value=2,
    ), patch(
        "app.services.interruption_distribution_service.invalidate_indicateurs_cache"
    ) as cache_mock, patch(
        "app.workers.tasks.indicateurs.calcul_saifi_saidi_task.delay"
    ) as delay_mock:
        result = await svc.valider(db, 1, user)

    assert result.statut == "valide"
    delay_mock.assert_called_once_with(1)
    cache_mock.assert_called_once_with(2, remise)
    db.commit.assert_awaited_once()


async def test_valider_en_cours_raises_422() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)
    user.user_roles[0].role.nom = "SUPERVISEUR"

    interruption = Interruption()
    interruption.id = 1
    interruption.service_id = 1
    interruption.statut = "en_cours"

    with patch(
        "app.services.interruption_distribution_service._get_interruption_accessible",
        new_callable=AsyncMock,
        return_value=interruption,
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.valider(db, 1, user)

    assert exc.value.status_code == 422


async def test_valider_bcc_role_raises_403() -> None:
    db = AsyncMock()
    user = _make_bcc(scope_service_id=1)

    with pytest.raises(HTTPException) as exc:
        await svc.valider(db, 1, user)

    assert exc.value.status_code == 403


def test_to_detail_response_includes_cause_libelle_from_base() -> None:
    """cause_libelle est déjà dans la réponse liste — ne doit pas être dupliqué au détail."""
    now = datetime(2026, 6, 12, 10, 30, 0)
    cause = Cause()
    cause.libelle = "Défaut matériel"

    interruption = Interruption()
    interruption.id = 59467
    interruption.numero_interruption = 42
    interruption.type_direction = "distribution"
    interruption.statut = "en_cours"
    interruption.service_id = 1
    interruption.feeder_id = 1
    interruption.poste_source_id = 1
    interruption.date_apparition = now
    interruption.cause_id = 1
    interruption.nature_id = 1
    interruption.siege_id = 1
    interruption.signalisation_id = 1
    interruption.is_force_majeure = False
    interruption.is_fugitive = False
    interruption.created_by_id = 1
    interruption.created_at = now
    interruption.updated_at = now
    interruption.cause = cause
    interruption.postes_interrompus = []

    distribution = InterruptionDistribution()
    distribution.is_programme = False
    distribution.has_extension_bt = False

    detail = svc._to_detail_response(interruption, distribution)

    assert detail.id == 59467
    assert detail.cause_libelle == "Défaut matériel"


def test_region_libelle_from_service_geo_chain() -> None:
    """region_libelle dérivée de service → agence → délégation → région."""
    from app.models.geo import Agence, Delegation, Region, Service

    region = Region()
    region.libelle = "Dakar"
    delegation = Delegation()
    delegation.region = region
    agence = Agence()
    agence.delegation = delegation
    service = Service()
    service.agence = agence

    interruption = Interruption()
    interruption.service = service

    assert svc._region_libelle(interruption) == "Dakar"
