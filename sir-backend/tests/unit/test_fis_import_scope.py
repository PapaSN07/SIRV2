"""Import FIS : périmètre RBAC par ligne et statut selon le droit de valider."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import fis_import_service as fis

M = "app.services.fis_import_service"


def _row(numero: int, service: str) -> fis.FisRow:
    return fis.FisRow(
        numero=numero,
        service_libelle=service,
        source_libelle="PS1",
        tension_kv=30.0,
        feeder_libelle="F1",
        nature_libelle="Permanent",
        cause_libelle="Défaut",
        siege_libelle=None,
        date_apparition=datetime(2026, 6, 1, 8, 0),
        date_remise=datetime(2026, 6, 1, 9, 0),
        duree_minutes=60,
        puissance_kw=1000.0,
        end_kwh=1000.0,
    )


def _db() -> MagicMock:
    db = MagicMock()
    db.flush = AsyncMock()
    savepoint = MagicMock(is_active=True, commit=AsyncMock(), rollback=AsyncMock())
    db.begin_nested = AsyncMock(return_value=savepoint)
    return db


SERVICES = {"DAKAR": SimpleNamespace(id=1), "THIES": SimpleNamespace(id=2)}


async def _scope_dakar_only(db, user, service_id: int) -> None:
    if service_id != 1:
        raise HTTPException(status_code=403, detail={"error": "Hors périmètre : region_id non autorisé"})


async def _run(rows, *, can_validate: bool, scoped: bool = True):
    db = _db()
    user = SimpleNamespace(id=7)
    with (
        patch(f"{M}.parse_fis_sheet", return_value=rows),
        patch(f"{M}._interruption_exists", new_callable=AsyncMock, return_value=False),
        patch(f"{M}._find_service", new_callable=AsyncMock, side_effect=lambda _db, lib: SERVICES.get(lib)),
        patch(f"{M}._find_poste_source", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._find_feeder", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._get_or_create_nature", new_callable=AsyncMock, return_value=SimpleNamespace(id=1, code="PERMANENT")),
        patch(f"{M}._get_or_create_cause", new_callable=AsyncMock, return_value=(SimpleNamespace(id=1), False)),
        patch(f"{M}._get_or_create_siege", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._can_validate", return_value=can_validate),
        patch.object(fis.distribution_rules, "_read_scope", return_value=object() if scoped else None),
        patch.object(fis.distribution_rules, "_ensure_service_in_write_scope", side_effect=_scope_dakar_only),
    ):
        result = await fis.import_fis_file(db, b"xlsx", current_user=user)
    added = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], fis.Interruption)]
    return result, added


async def test_lignes_hors_perimetre_rejetees() -> None:
    result, added = await _run([_row(1, "DAKAR"), _row(2, "THIES")], can_validate=False)
    assert result.stats.importees == 1
    assert result.stats.erreurs == 1
    assert "Hors périmètre" in result.stats.erreurs_detail[0]
    assert [i.service_id for i in added] == [1]


async def test_service_inconnu_rejete_pour_un_compte_avec_perimetre() -> None:
    result, added = await _run([_row(3, "INCONNU")], can_validate=False)
    assert result.stats.importees == 0
    assert "périmètre invérifiable" in result.stats.erreurs_detail[0]
    assert added == []


@pytest.mark.parametrize(("can_validate", "statut", "validated_by"), [(False, "cloture", None), (True, "valide", 7)])
async def test_statut_selon_droit_de_valider(can_validate: bool, statut: str, validated_by: int | None) -> None:
    _, added = await _run([_row(4, "DAKAR")], can_validate=can_validate)
    assert added[0].statut == statut
    assert added[0].validated_by_id == validated_by
