"""Matrice des rôles : création, garde-fous contre l'auto-attribution de droits."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.schemas.admin import RoleCreate, RoleUpdate
from app.services import admin_advanced_service as svc

_PERMS = {
    1: SimpleNamespace(id=1, ressource="indicateurs", action="read", description=None),
    2: SimpleNamespace(id=2, ressource="rapports", action="read", description=None),
    9: SimpleNamespace(id=9, ressource="admin_roles", action="update", description=None),
}


def _user(*roles: str) -> Any:
    return SimpleNamespace(id=7, user_roles=[SimpleNamespace(role=SimpleNamespace(nom=r)) for r in roles])


def _role(rid: int, nom: str, perm_ids: list[int]) -> Any:
    return SimpleNamespace(
        id=rid,
        nom=nom,
        description=None,
        is_active=True,
        role_permissions=[SimpleNamespace(permission_id=p, permission=_PERMS[p]) for p in perm_ids],
    )


class _Db:
    async def flush(self) -> None:
        return None

    def expire(self, _obj: Any) -> None:
        return None


@pytest.fixture
def roles(monkeypatch: pytest.MonkeyPatch) -> dict[int, Any]:
    stock: dict[int, Any] = {1: _role(1, "BCC", [1]), 2: _role(2, "ADMIN_SCR", [1, 9])}

    async def get_role(_db: Any, rid: int) -> Any:
        return stock.get(rid)

    async def par_nom(_db: Any, nom: str) -> Any:
        return next((r for r in stock.values() if r.nom == nom), None)

    async def perms(_db: Any, ids: list[int]) -> list[Any]:
        return [_PERMS[i] for i in ids if i in _PERMS]

    async def creer(_db: Any, nom: str, description: str | None) -> Any:
        stock[3] = _role(3, nom, [])
        return stock[3]

    async def remplacer(_db: Any, rid: int, ids: list[int]) -> None:
        stock[rid].role_permissions = [SimpleNamespace(permission_id=i, permission=_PERMS[i]) for i in ids]

    async def comptes(_db: Any) -> dict[int, int]:
        return {}

    async def audit(*_a: Any, **_k: Any) -> None:
        return None

    for nom, fn in {
        "get_role": get_role,
        "role_par_nom": par_nom,
        "permissions_par_ids": perms,
        "creer_role": creer,
        "remplacer_permissions": remplacer,
        "nombre_utilisateurs_par_role": comptes,
    }.items():
        monkeypatch.setattr(svc.role_repository, nom, fn)
    monkeypatch.setattr(svc, "log_audit", audit)
    return stock


async def test_creation_role_avec_droits(roles: dict) -> None:
    res = await svc.create_role(_Db(), _user("ADMIN_SCR"), RoleCreate(nom="chef_unite", permission_ids=[1, 2]))  # type: ignore[arg-type]
    assert res.nom == "CHEF_UNITE" and not res.systeme
    assert {(p.ressource, p.action) for p in res.permissions} == {("indicateurs", "read"), ("rapports", "read")}


async def test_doublon_refuse(roles: dict) -> None:
    with pytest.raises(HTTPException) as exc:
        await svc.create_role(_Db(), _user("ADMIN_SCR"), RoleCreate(nom="bcc"))  # type: ignore[arg-type]
    assert exc.value.status_code == 409


async def test_admin_ne_donne_pas_la_gestion_des_roles(roles: dict) -> None:
    with pytest.raises(HTTPException) as exc:
        await svc.update_role(_Db(), _user("ADMIN_SCR"), 1, RoleUpdate(permission_ids=[1, 9]))  # type: ignore[arg-type]
    assert exc.value.status_code == 403


async def test_admin_ne_modifie_pas_son_propre_role(roles: dict) -> None:
    with pytest.raises(HTTPException) as exc:
        await svc.update_role(_Db(), _user("ADMIN_SCR"), 2, RoleUpdate(permission_ids=[1, 2, 9]))  # type: ignore[arg-type]
    assert exc.value.status_code == 403


async def test_role_systeme_non_desactivable_mais_droits_modifiables(roles: dict) -> None:
    with pytest.raises(HTTPException):
        await svc.update_role(_Db(), _user("ADMIN_SCR"), 1, RoleUpdate(is_active=False))  # type: ignore[arg-type]
    res = await svc.update_role(_Db(), _user("ADMIN_SCR"), 1, RoleUpdate(permission_ids=[1, 2]))  # type: ignore[arg-type]
    assert len(res.permissions) == 2
