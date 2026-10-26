"""Le seed RBAC ne crée le compte superadmin.dev que sur demande explicite."""

from itertools import count
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.seed.seed_rbac import seed_rbac
from app.models.utilisateurs import Utilisateur


def _db() -> AsyncMock:
    ids = count(1)
    db = AsyncMock()
    db.flush = AsyncMock()

    def _add(obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = next(ids)

    db.add = MagicMock(side_effect=_add)

    async def _execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        result.all.return_value = []
        return result

    db.execute = _execute
    return db


def _users(db: AsyncMock) -> list[Utilisateur]:
    return [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Utilisateur)]


async def test_seed_rbac_par_defaut_ne_cree_aucun_compte() -> None:
    db = _db()
    await seed_rbac(db)
    assert _users(db) == []


async def test_superadmin_cree_seulement_sur_demande() -> None:
    db = _db()
    await seed_rbac(db, with_superadmin=True, superadmin_password="Mot-de-passe-local-1")
    assert [u.login for u in _users(db)] == ["superadmin.dev"]


async def test_superadmin_sans_mot_de_passe_refuse() -> None:
    with pytest.raises(ValueError, match="superadmin_password"):
        await seed_rbac(_db(), with_superadmin=True)
