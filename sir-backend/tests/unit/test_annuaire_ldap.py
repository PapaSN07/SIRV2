"""Recherche dans l'annuaire : filtre LDAP échappé, comptes désactivés exclus, comptes déjà présents signalés."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.services import admin_utilisateur_service as svc
from app.services import ldap_service


class _Conn:
    def __init__(self) -> None:
        self.filtre = ""
        self.entries = [
            SimpleNamespace(entry_attributes_as_dict={"sAMAccountName": ["adiop"], "givenName": ["Awa"], "sn": ["Diop"], "mail": ["awa.diop@senelec.sn"], "employeeID": ["12345"]}),
            SimpleNamespace(entry_attributes_as_dict={"sAMAccountName": ["mfall"], "givenName": ["Moussa"], "sn": ["Fall"]}),
        ]

    def search(self, **kwargs: Any) -> bool:
        self.filtre = kwargs["search_filter"]
        return True

    def unbind(self) -> None:
        return None


def test_filtre_echappe_et_comptes_desactives_exclus(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn()
    monkeypatch.setattr(ldap_service, "_service_connection", lambda **_k: conn)
    monkeypatch.setattr(ldap_service.settings, "ldap_enabled", True, raising=False)
    monkeypatch.setattr(type(ldap_service.settings), "ldap_is_configured", property(lambda _s: True))
    res = ldap_service.rechercher_annuaire("diop *)(")
    assert "userAccountControl:1.2.840.113556.1.4.803:=2" in conn.filtre
    assert "\\2a\\29\\28" in conn.filtre  # « *)( » échappé
    assert [e.login for e in res] == ["adiop", "mfall"]
    assert res[0].matricule == "12345"


async def test_comptes_deja_presents_signales(monkeypatch: pytest.MonkeyPatch) -> None:
    entree = ldap_service.AnnuaireEntree("ADiop", "Awa", "Diop", None, None, None, None, None, None)
    monkeypatch.setattr(ldap_service, "rechercher_annuaire", lambda texte: [entree])
    monkeypatch.setattr(svc, "_get_admin_direction", lambda u: "distribution")

    async def existants(_db: Any, logins: list[str]) -> set[str]:
        return {"adiop"}

    monkeypatch.setattr(svc.admin_repo, "logins_existants", existants)
    res = await svc.rechercher_annuaire(None, None, "diop")  # type: ignore[arg-type]
    assert res[0].deja_dans_sir is True
