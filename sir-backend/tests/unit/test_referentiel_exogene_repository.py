"""Repository référentiel — facteur exogène des causes (docs/fusion_suivi_incidents.md, section 12).

``create`` / ``update`` acceptent ``est_exogene`` et ne le posent que pour ``causes`` :
création sans valeur → False ; mise à jour avec None → inchangé ; False est bien écrit (pas confondu avec None).
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.sql.dml import Update

from app.models.referentiel import Cause, Nature
from app.repositories import referentiel_repository as repo

_GET_BY_ID = "app.repositories.referentiel_repository.get_by_id"


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _ajoute(db: AsyncMock) -> Any:
    db.add.assert_called_once()
    return db.add.call_args.args[0]


def _params(db: AsyncMock) -> dict[str, Any]:
    statement = db.execute.await_args.args[0]
    assert isinstance(statement, Update)
    return dict(statement.compile().params)


async def test_create_cause_pose_est_exogene_true() -> None:
    db = _db()
    await repo.create(db, "causes", code="C01", libelle="Malveillance", type_reseau="distribution", est_exogene=True)
    record = _ajoute(db)
    assert isinstance(record, Cause)
    assert record.est_exogene is True


async def test_create_cause_sans_valeur_pose_false() -> None:
    db = _db()
    await repo.create(db, "causes", code="C02", libelle="Défaut", type_reseau="distribution", est_exogene=None)
    assert _ajoute(db).est_exogene is False


async def test_create_cause_sans_argument_pose_false() -> None:
    db = _db()
    await repo.create(db, "causes", code="C03", libelle="Défaut", type_reseau="distribution")
    assert _ajoute(db).est_exogene is False


async def test_create_nature_ignore_est_exogene() -> None:
    db = _db()
    await repo.create(db, "natures", code="N01", libelle="Coupure", est_exogene=True)
    record = _ajoute(db)
    assert isinstance(record, Nature)
    assert not hasattr(record, "est_exogene")


async def test_update_cause_pose_est_exogene_false() -> None:
    db = _db()
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=SimpleNamespace(id=1)):
        await repo.update(db, "causes", 1, est_exogene=False)
    assert _params(db)["est_exogene"] is False


async def test_update_cause_pose_est_exogene_true() -> None:
    db = _db()
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=SimpleNamespace(id=1)):
        await repo.update(db, "causes", 1, est_exogene=True)
    assert _params(db)["est_exogene"] is True


async def test_update_cause_est_exogene_none_inchange() -> None:
    db = _db()
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=SimpleNamespace(id=1)):
        await repo.update(db, "causes", 1, libelle="Nouveau", est_exogene=None)
    params = _params(db)
    assert "est_exogene" not in params
    assert params["libelle"] == "Nouveau"


async def test_update_nature_ignore_est_exogene() -> None:
    db = _db()
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=SimpleNamespace(id=3)):
        await repo.update(db, "natures", 3, est_exogene=True)
    db.execute.assert_not_awaited()
