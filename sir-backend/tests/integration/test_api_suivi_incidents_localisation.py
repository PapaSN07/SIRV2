"""GET /api/v1/suivi-incidents/localisation — onglet Localisation (spécification étape 6a, §11).

Paramètres : filtres communs + ``page`` (≥ 1, défaut 1), ``size`` (1 à 100, défaut 20) ; autre
valeur → 422 **enveloppé**. Réponse ``ApiResponse[LocalisationSuivi]`` :

- ``postes_touches``, ``postes_localises``, ``taux`` (localisés ÷ touchés, 0 si aucun) ;
- ``par_mode`` : ``{rapprochement, nom}`` ;
- ``postes_sources`` : par poste source **du feeder du poste**
  ``{id, libelle, postes_touches, non_localises, taux}``, triés par non_localises décroissant puis
  libellé, « Non renseigné » (id null : poste sans feeder ou feeder sans poste source) en dernier ;
- ``non_localises`` : ``{total, page, size, items}``, items
  ``{poste_id, code, libelle, feeder, poste_source, interruptions}`` triés par interruptions
  décroissantes puis libellé.

Mêmes règles de localisation que /carte (pas de limite de 3 000 ici). Cache Redis 1 h
``suivi:localisation:{empreinte des filtres résolus, page et size}``.

Données : ``tests/integration/_donnees_carte_suivi.py``.
Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration._donnees_carte_suivi import (  # noqa: F401 (fixtures)
    PERIODE_VIDE,
    SEMAINE,
    _make_user,
    appeler,
    client_carte,
    erreur_enveloppee,
    session_carte,
)

pytestmark = pytest.mark.asyncio

URL = "/api/v1/suivi-incidents/localisation"
CHAMPS_REPONSE = {"postes_touches", "postes_localises", "taux", "par_mode", "postes_sources", "non_localises"}
CHAMPS_POSTE_SOURCE = {"id", "libelle", "postes_touches", "non_localises", "taux"}
CHAMPS_PAGE = {"total", "page", "size", "items"}
CHAMPS_NON_LOCALISE = {"poste_id", "code", "libelle", "feeder", "poste_source", "interruptions"}

# Non localisés en national sur S47 : interruptions décroissantes puis libellé
NON_LOCALISES = [
    # (poste_id, code, libellé, feeder, poste source, interruptions)
    (4, "P-DELTA", "DELTA", "BEL AIR 2", "SOCOCIM", 2),
    (7, "P-GOLF", "GOLF", None, None, 1),
    (10, "P-JULIET", "JULIET", "HANN DEPART 2", "HANN", 1),
    (11, "P-KILO", "KILO", "KAOLACK VILLE", "KAOLACK", 1),
    (12, "P-LIMA", "LIMA", None, None, 1),
    (13, "P-MIKE", "MIKE", "KAOLACK VILLE", "KAOLACK", 1),
]


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **(params or {})})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    data = corps["data"]
    assert set(data) == CHAMPS_REPONSE, data
    assert set(data["par_mode"]) == {"rapprochement", "nom"}, data["par_mode"]
    for ligne in data["postes_sources"]:
        assert set(ligne) == CHAMPS_POSTE_SOURCE, ligne
    assert set(data["non_localises"]) == CHAMPS_PAGE, data["non_localises"]
    for item in data["non_localises"]["items"]:
        assert set(item) == CHAMPS_NON_LOCALISE, item
    return data


def _items(data: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (i["poste_id"], i["code"], i["libelle"], i["feeder"], i["poste_source"], i["interruptions"])
        for i in data["non_localises"]["items"]
    ]


def _nationale() -> Any:
    return _make_user("ADMIN_SAQS")


# --------------------------------------------------------------------------------------------
# Taux et modes
# --------------------------------------------------------------------------------------------


async def test_taux_et_par_mode(client_carte: AsyncClient) -> None:
    """13 postes touchés, 7 localisés : rapprochement ALPHA, BRAVO ; nom CHARLIE, ECHO, FOXTROT,
    HOTEL, INDIA."""
    data = await _ok(client_carte, _nationale())
    assert data["postes_touches"] == 13
    assert data["postes_localises"] == 7
    assert data["taux"] == pytest.approx(7 / 13, abs=1e-4)
    assert data["par_mode"] == {"rapprochement": 2, "nom": 5}


async def test_meme_compte_que_la_carte(client_carte: AsyncClient) -> None:
    localisation = await _ok(client_carte, _nationale())
    response = await appeler(client_carte, "/api/v1/suivi-incidents/carte", _nationale(), SEMAINE)
    assert response.status_code == 200, response.text
    carte = response.json()["data"]
    assert localisation["postes_touches"] == carte["postes_touches"]
    assert localisation["postes_localises"] == carte["postes_localises"]


async def test_periode_vide_taux_nul(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), PERIODE_VIDE)
    assert data["postes_touches"] == 0
    assert data["postes_localises"] == 0
    assert data["taux"] == 0
    assert data["par_mode"] == {"rapprochement": 0, "nom": 0}
    assert data["postes_sources"] == []
    assert data["non_localises"] == {"total": 0, "page": 1, "size": 20, "items": []}


# --------------------------------------------------------------------------------------------
# Postes sources
# --------------------------------------------------------------------------------------------


async def test_postes_sources_par_le_feeder_du_poste(client_carte: AsyncClient) -> None:
    """KAOLACK {FOXTROT, KILO, MIKE} 2 non localisés ; HANN {ALPHA, BRAVO, CHARLIE, JULIET} 1 ;
    SOCOCIM {DELTA, ECHO} 1 ; Non renseigné {GOLF, HOTEL, LIMA (sans feeder), INDIA (feeder sans
    poste source)} 2 — en dernier malgré ses 2 non localisés.

    CHARLIE est touché par 602 (interruption sur le feeder 1) mais son feeder est le 2 : compté chez
    HANN par son propre feeder ; 608 (sans poste source ni feeder saisis) ne range pas INDIA en
    « Non renseigné » par l'interruption mais par son feeder."""
    data = await _ok(client_carte, _nationale())
    lignes = [(l["id"], l["libelle"], l["postes_touches"], l["non_localises"]) for l in data["postes_sources"]]
    assert lignes == [
        (3, "KAOLACK", 3, 2),
        (1, "HANN", 4, 1),
        (2, "SOCOCIM", 2, 1),
        (None, "Non renseigné", 4, 2),
    ]
    taux = [l["taux"] for l in data["postes_sources"]]
    assert taux == pytest.approx([1 / 3, 3 / 4, 1 / 2, 1 / 2], abs=1e-4)


async def test_postes_sources_somme_egale_aux_totaux(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale())
    assert sum(l["postes_touches"] for l in data["postes_sources"]) == data["postes_touches"]
    assert sum(l["non_localises"] for l in data["postes_sources"]) == data["non_localises"]["total"]


# --------------------------------------------------------------------------------------------
# Non localisés (pagination)
# --------------------------------------------------------------------------------------------


async def test_non_localises_par_defaut(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale())
    page = data["non_localises"]
    assert (page["total"], page["page"], page["size"]) == (6, 1, 20)
    assert _items(data) == NON_LOCALISES


async def test_non_localises_page_2(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), {"page": 2, "size": 2})
    page = data["non_localises"]
    assert (page["total"], page["page"], page["size"]) == (6, 2, 2)
    assert _items(data) == NON_LOCALISES[2:4]


async def test_non_localises_derniere_page_partielle_et_au_dela(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), {"page": 2, "size": 4})
    assert _items(data) == NON_LOCALISES[4:]
    au_dela = await _ok(client_carte, _nationale(), {"page": 4, "size": 2})
    assert au_dela["non_localises"] == {"total": 6, "page": 4, "size": 2, "items": []}


async def test_pagination_sans_effet_sur_les_totaux(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), {"page": 3, "size": 1})
    assert data["postes_touches"] == 13
    assert data["postes_localises"] == 7
    assert len(data["postes_sources"]) == 4


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": "abc"},
        {"page": "1.5"},
        {"size": 0},
        {"size": 101},
        {"size": -5},
        {"size": "x"},
        {"debut": "2026-11-20", "fin": "2026-11-14"},
        {"reseau": "bt"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_carte: AsyncClient, params: dict[str, Any]) -> None:
    response = await appeler(client_carte, URL, _nationale(), {**SEMAINE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


@pytest.mark.parametrize("size", [1, 100])
async def test_bornes_de_size_acceptees(client_carte: AsyncClient, size: int) -> None:
    data = await _ok(client_carte, _nationale(), {"size": size})
    assert data["non_localises"]["size"] == size
    assert len(data["non_localises"]["items"]) == min(size, 6)


# --------------------------------------------------------------------------------------------
# Filtres
# --------------------------------------------------------------------------------------------


async def test_filtre_nature(client_carte: AsyncClient) -> None:
    """DELESTAGE : ALPHA, CHARLIE, FOXTROT localisés, JULIET non localisé (1 interruption)."""
    data = await _ok(client_carte, _nationale(), {"nature_id": 3})
    assert data["postes_touches"] == 4
    assert data["postes_localises"] == 3
    assert data["par_mode"] == {"rapprochement": 1, "nom": 2}
    assert _items(data) == [(10, "P-JULIET", "JULIET", "HANN DEPART 2", "HANN", 1)]


# --------------------------------------------------------------------------------------------
# Authentification et périmètre
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client_carte: AsyncClient) -> None:
    response = await client_carte.get(URL, params=SEMAINE)
    assert response.status_code in (401, 403)


async def test_sans_permission_indicateurs_read_403(client_carte: AsyncClient) -> None:
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await appeler(client_carte, URL, user, SEMAINE)
    assert response.status_code == 403


async def test_role_hors_regle_des_indicateurs_403(client_carte: AsyncClient) -> None:
    response = await appeler(client_carte, URL, _make_user("DISPATCHER"), SEMAINE)
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national(client_carte: AsyncClient, role: str) -> None:
    data = await _ok(client_carte, _make_user(role))
    assert data["postes_touches"] == 13
    assert data["non_localises"]["total"] == 6


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_carte: AsyncClient, role: str) -> None:
    """Région 2 : FOXTROT localisé, KILO et MIKE non localisés, tous sous KAOLACK."""
    data = await _ok(client_carte, _make_user(role, scope_service_id=2))
    assert data["postes_touches"] == 3
    assert data["postes_localises"] == 1
    assert data["taux"] == pytest.approx(1 / 3, abs=1e-4)
    assert [(l["id"], l["postes_touches"], l["non_localises"]) for l in data["postes_sources"]] == [(3, 3, 2)]
    assert [i[2] for i in _items(data)] == ["KILO", "MIKE"]


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_carte: AsyncClient, role: str) -> None:
    response = await appeler(client_carte, URL, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 1})
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _make_user("BCC", scope_service_id=2), {"service_id": 1})
    assert data["postes_touches"] == 0
    assert data["non_localises"]["items"] == []
    assert data["postes_sources"] == []


async def test_superviseur_limite_a_son_service(client_carte: AsyncClient) -> None:
    """SDPG (604, 605) : ECHO localisé, DELTA non localisé (2 interruptions)."""
    data = await _ok(client_carte, _make_user("SUPERVISEUR", scope_service_id=2))
    assert data["postes_touches"] == 2
    assert data["postes_localises"] == 1
    assert _items(data) == [(4, "P-DELTA", "DELTA", "BEL AIR 2", "SOCOCIM", 2)]


async def test_superviseur_autre_service_403(client_carte: AsyncClient) -> None:
    response = await appeler(
        client_carte, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**SEMAINE, "service_id": 2}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_cle_suivi_localisation_ttl_une_heure(client_carte: AsyncClient, fake_redis: Any) -> None:
    await _ok(client_carte, _nationale())
    cles = [c async for c in fake_redis.scan_iter("suivi:localisation:*")]
    assert cles, "aucune clé suivi:localisation:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_deuxieme_appel_servi_par_le_cache(client_carte: AsyncClient, session_carte: AsyncSession) -> None:
    premier = await _ok(client_carte, _nationale())
    await session_carte.execute(text("DELETE FROM poste_interruptions"))
    await session_carte.commit()
    second = await _ok(client_carte, _nationale())
    assert second == premier


async def test_cache_distinct_par_page_et_perimetre(client_carte: AsyncClient) -> None:
    page_1 = await _ok(client_carte, _nationale(), {"page": 1, "size": 2})
    page_2 = await _ok(client_carte, _nationale(), {"page": 2, "size": 2})
    regional = await _ok(client_carte, _make_user("BCC", scope_service_id=2), {"page": 1, "size": 2})
    assert _items(page_1) == NON_LOCALISES[:2]
    assert _items(page_2) == NON_LOCALISES[2:4]
    assert regional["postes_touches"] == 3
