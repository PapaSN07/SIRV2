"""Administration des objectifs : une ligne nationale puis une par région ; droits Admin SCR / SAQS."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.schemas.indicateurs import ObjectifsAdminUpdate
from app.services import pilotage_service


def _user(role: str) -> Any:
    return SimpleNamespace(user_roles=[SimpleNamespace(role=SimpleNamespace(nom=role))], is_superadmin=False)


class _Redis:
    def __init__(self) -> None:
        self.supprimees: list[str] = []

    async def delete(self, key: str) -> None:
        self.supprimees.append(key)


class _Db:
    async def flush(self) -> None:
        return None


@pytest.fixture
def base(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[int | None, str], float]:
    stock: dict[tuple[int | None, str], float] = {(None, "END"): 1200.0, (2, "SAIFI"): 4.5}

    async def lister(_db: Any, annee: int) -> list[Any]:
        return [SimpleNamespace(region_id=r, code=c, valeur_annuelle=v) for (r, c), v in stock.items()]

    async def regions(_db: Any) -> list[tuple[int, str]]:
        return [(1, "Dakar"), (2, "Régions")]

    async def upsert(_db: Any, *, annee: int, code: str, valeur_annuelle: float, region_id: int | None) -> None:
        stock[(region_id, code)] = valeur_annuelle

    monkeypatch.setattr(pilotage_service.repo, "list_objectifs_annee", lister)
    monkeypatch.setattr(pilotage_service.repo, "list_regions_actives", regions)
    monkeypatch.setattr(pilotage_service.repo, "upsert_objectif", upsert)
    monkeypatch.setattr(pilotage_service, "is_superadmin", lambda u: False)
    return stock


async def test_lignes_nationale_puis_regions(base: dict) -> None:
    res = await pilotage_service.lister_objectifs_admin(_Db(), _user("ADMIN_SCR"), 2026)  # type: ignore[arg-type]
    assert [l.libelle for l in res.lignes] == ["National", "Dakar", "Régions"]
    assert res.lignes[0].end_mwh == 1200.0
    assert res.lignes[2].saifi == 4.5 and res.lignes[1].saifi is None


async def test_enregistrement_region_et_cache(base: dict) -> None:
    redis = _Redis()
    body = ObjectifsAdminUpdate(annee=2026, region_id=1, saidi=6.2)
    res = await pilotage_service.enregistrer_objectifs_admin(_Db(), redis, _user("ADMIN_SAQS"), body)  # type: ignore[arg-type]
    assert res.lignes[1].saidi == 6.2
    assert len(redis.supprimees) == 24


async def test_bcc_refuse(base: dict) -> None:
    with pytest.raises(HTTPException) as exc:
        await pilotage_service.lister_objectifs_admin(_Db(), _user("BCC"), 2026)  # type: ignore[arg-type]
    assert exc.value.status_code == 403
