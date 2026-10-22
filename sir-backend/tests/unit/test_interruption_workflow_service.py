"""Tests unitaires — workflow par étapes chaînées (etapes_workflow / workflows)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.interruption_workflow import EtapeWorkflow, Workflow
from app.schemas.interruption_workflow import WorkflowEtapeUpdate
from app.services import interruption_workflow_service as svc
from app.services.interruption_workflow_service import (
    _split_localisation_troncon,
    compute_etats,
    order_etapes,
)

_SVC = "app.services.interruption_workflow_service"


def _etape(etape_id: int, code: str, ordre: int, suivante: int | None) -> EtapeWorkflow:
    etape = EtapeWorkflow()
    etape.id = etape_id
    etape.code = code
    etape.libelle_etape_workflow = code.capitalize()
    etape.ordre = ordre
    etape.etape_suivante_id = suivante
    return etape


def _chaine() -> list[EtapeWorkflow]:
    return [
        _etape(1, "declenchement", 1, 2),
        _etape(2, "interpellation_pdm", 2, 3),
        _etape(3, "tronconnement", 3, 4),
        _etape(4, "localisation", 4, 5),
        _etape(5, "reparation", 5, 6),
        _etape(6, "remise", 6, None),
    ]


def _row(etape_id: int, date_fin: datetime | None) -> Workflow:
    row = Workflow()
    row.id = etape_id * 10
    row.etape_workflow_id = etape_id
    row.date_debut = datetime(2026, 6, 19, 8, 0)
    row.date_fin = date_fin
    row.troncon = None
    row.troncon_sig = None
    return row


def test_split_localisation_troncon_with_separator() -> None:
    amont, aval = _split_localisation_troncon("POSTE THIONA - EDK")
    assert amont == "POSTE THIONA"
    assert aval == "EDK"


def test_order_etapes_follows_chain_not_ordre() -> None:
    etapes = _chaine()
    # ordre volontairement incohérent : la chaîne etape_suivante_id prime
    etapes[0].ordre = 99
    ordered = order_etapes(list(reversed(etapes)))
    assert [e.id for e in ordered] == [1, 2, 3, 4, 5, 6]


def test_compute_etats_without_rows_all_are_open() -> None:
    etats = compute_etats(_chaine(), {})
    assert all(etats[i] == "active" for i in range(1, 7))


def test_compute_etats_date_fin_marks_done_and_keeps_next_open() -> None:
    rows = {
        1: _row(1, datetime(2026, 6, 19, 8, 15)),
        2: _row(2, None),
    }
    etats = compute_etats(_chaine(), rows)
    assert etats[1] == "terminee"
    assert etats[2] == "active"
    assert etats[3] == "active"


def test_compute_etats_without_date_fin_does_not_lock_next() -> None:
    etats = compute_etats(_chaine(), {1: _row(1, None)})
    assert etats[1] == "active"
    assert etats[2] == "active"


@pytest.fixture
def interruption() -> SimpleNamespace:
    return SimpleNamespace(id=1, statut="en_cours", localisation=None)


def _patch_common(interruption: SimpleNamespace, rows: list[Workflow]):
    return (
        patch(f"{_SVC}._ensure_can_write_workflow"),
        patch(f"{_SVC}._ensure_interruption_accessible", AsyncMock(return_value=interruption)),
        patch(f"{_SVC}.workflow_repo.list_etapes", AsyncMock(return_value=_chaine())),
        patch(f"{_SVC}.workflow_repo.list_workflows", AsyncMock(return_value=rows)),
        patch(f"{_SVC}.workflow_repo.upsert_workflow", AsyncMock()),
        patch(f"{_SVC}.log_audit", AsyncMock()),
        patch(f"{_SVC}._build_response", AsyncMock(return_value="ok")),
    )


async def test_update_etape_can_skip_previous(interruption: SimpleNamespace) -> None:
    db = MagicMock()
    db.commit = AsyncMock()
    patches = _patch_common(interruption, [])
    with patches[0], patches[1], patches[2], patches[3], patches[4] as upsert, patches[5], patches[6]:
        result = await svc.update_etape(db, 1, 3, WorkflowEtapeUpdate(observation="x"), MagicMock(id=7))
    assert result == "ok"
    upsert.assert_awaited_once()


async def test_update_etape_not_en_cours_returns_422(interruption: SimpleNamespace) -> None:
    interruption.statut = "cloture"
    db = MagicMock()
    patches = _patch_common(interruption, [])
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        with pytest.raises(HTTPException) as exc:
            await svc.update_etape(db, 1, 1, WorkflowEtapeUpdate(observation="x"), MagicMock())
    assert exc.value.status_code == 422


async def test_update_etape_fin_before_debut_returns_422(interruption: SimpleNamespace) -> None:
    db = MagicMock()
    patches = _patch_common(interruption, [])
    body = WorkflowEtapeUpdate(
        date_debut=datetime(2026, 6, 19, 9, 0),
        date_fin=datetime(2026, 6, 19, 8, 0),
    )
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        with pytest.raises(HTTPException) as exc:
            await svc.update_etape(db, 1, 1, body, MagicMock())
    assert exc.value.status_code == 422


async def test_update_etape_active_strips_troncon_fields(interruption: SimpleNamespace) -> None:
    db = MagicMock()
    db.commit = AsyncMock()
    patches = _patch_common(interruption, [_row(1, datetime(2026, 6, 19, 8, 15))])
    body = WorkflowEtapeUpdate(observation="PDM appelé", troncon_sig_id=42)
    with patches[0], patches[1], patches[2], patches[3], patches[4] as upsert, patches[5], patches[6]:
        result = await svc.update_etape(db, 1, 2, body, MagicMock(id=7))
    assert result == "ok"
    upsert.assert_awaited_once()
    values = upsert.await_args.args[3]
    assert values == {"observation": "PDM appelé"}
    db.commit.assert_awaited_once()
