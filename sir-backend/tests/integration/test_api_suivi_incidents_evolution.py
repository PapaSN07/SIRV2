"""GET /api/v1/suivi-incidents/evolution — onglet Évolution (spécification étape 4, §9).

Paramètres : filtres communs + ``granularite`` = auto (défaut) | jour | semaine | mois ; autre
valeur → 422 enveloppé ; ``jour`` sur plus de 366 jours → 422. ``auto`` : jour ≤ 31 jours,
semaine SENELEC ≤ 186 jours, mois sinon.

Réponse ``ApiResponse[EvolutionSuivi]`` : ``granularite`` (appliquée, jamais « auto »), ``points``
= tous les intervalles de la période, vides compris, dans l'ordre :
``{debut, fin, libelle, nombre, duree_heures, end_mwh, natures: {incident, delestage, travaux, autre}}``.
Somme des ``nombre`` = ``kpi.nombre_interruptions`` de /vue-ensemble pour les mêmes filtres.

Données : ``tests/integration/_donnees_suivi_incidents.py``.
Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration._donnees_suivi_incidents import (  # noqa: F401 (fixtures)
    SEMAINE,
    _make_user,
    appeler,
    client_suivi,
    erreur_enveloppee,
    session_suivi,
)

pytestmark = pytest.mark.asyncio

URL = "/api/v1/suivi-incidents/evolution"
URL_VUE = "/api/v1/suivi-incidents/vue-ensemble"
APPROX = {"abs": 0.01}
CHAMPS_POINT = {"debut", "fin", "libelle", "nombre", "duree_heures", "end_mwh", "natures"}
CATEGORIES = {"incident", "delestage", "travaux", "autre"}


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **(params or {})})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    data = corps["data"]
    assert {"granularite", "points"} <= set(data), data
    for point in data["points"]:
        assert set(point) == CHAMPS_POINT, point
        assert set(point["natures"]) == CATEGORIES, point
        assert sum(point["natures"].values()) == point["nombre"], point
    return data


def _nombres(data: dict[str, Any]) -> list[int]:
    return [p["nombre"] for p in data["points"]]


def _bornes(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(p["debut"], p["fin"], p["libelle"]) for p in data["points"]]


def _natures(point: dict[str, Any]) -> dict[str, int]:
    return {cle: v for cle, v in point["natures"].items() if v}


def _point(point: dict[str, Any], nombre: int, duree_h: float, end: float, natures: dict[str, int]) -> None:
    assert point["nombre"] == nombre, point
    assert point["duree_heures"] == pytest.approx(duree_h, **APPROX), point
    assert point["end_mwh"] == pytest.approx(end, **APPROX), point
    assert _natures(point) == natures, point


async def _kpi_nombre(client: AsyncClient, user: Any, params: dict[str, Any]) -> int:
    response = await appeler(client, URL_VUE, user, {**SEMAINE, **params})
    assert response.status_code == 200, response.text
    return response.json()["data"]["kpi"]["nombre_interruptions"]


# --------------------------------------------------------------------------------------------
# Granularité jour (auto sur la semaine S47)
# --------------------------------------------------------------------------------------------


async def test_semaine_s47_auto_par_jour(client_suivi: AsyncClient) -> None:
    """S47 (7 jours) → jour ; 7 points, sommes et natures exactes par jour."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    assert data["granularite"] == "jour"
    assert _bornes(data) == [
        (f"2026-11-{j}", f"2026-11-{j}", f"{j}/11") for j in ("14", "15", "16", "17", "18", "19", "20")
    ]
    j14, j15, j16, j17, j18, j19, j20 = data["points"]
    _point(j14, 2, 130 / 60, 2.6, {"incident": 1, "autre": 1})  # 101, 108
    _point(j15, 1, 0.5, 0.5, {"incident": 1})  # 102
    _point(j16, 1, 1.0, 4.0, {"delestage": 1})  # 103
    _point(j17, 2, 255 / 60, 1.05, {"travaux": 1, "incident": 1})  # 104, 109
    _point(j18, 1, 0.0, 0.0, {"autre": 1})  # 105 en cours, sans durée ni END
    _point(j19, 1, 1.5, 1.5, {"autre": 1})  # 106 (HTB autres)
    _point(j20, 1, 0.75, 0.2, {"incident": 1})  # 107 à 23 h 59


async def test_granularite_auto_explicite_identique(client_suivi: AsyncClient) -> None:
    defaut = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    auto = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"granularite": "auto"})
    assert auto["granularite"] == "jour"
    assert auto["points"] == defaut["points"]


async def test_jours_vides_presents_a_zero(client_suivi: AsyncClient) -> None:
    """Semaine sans interruption : 7 points à 0, natures à 0."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"debut": "2026-12-05", "fin": "2026-12-11"})
    assert data["granularite"] == "jour"
    assert len(data["points"]) == 7
    for point in data["points"]:
        _point(point, 0, 0.0, 0.0, {})
        assert point["natures"] == {"incident": 0, "delestage": 0, "travaux": 0, "autre": 0}


async def test_jours_changement_d_annee(client_suivi: AsyncClient) -> None:
    """30/12/2026 → 02/01/2027 : 307 le 31/12, 308 le 02/01."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"debut": "2026-12-30", "fin": "2027-01-02"})
    assert data["granularite"] == "jour"
    assert [p["libelle"] for p in data["points"]] == ["30/12", "31/12", "01/01", "02/01"]
    assert _nombres(data) == [0, 1, 0, 1]
    assert data["points"][2]["debut"] == "2027-01-01"


# --------------------------------------------------------------------------------------------
# Granularité semaine
# --------------------------------------------------------------------------------------------


async def test_semaine_forcee_rognee_aux_bornes(client_suivi: AsyncClient) -> None:
    """Mardi 10/11 → mercredi 18/11, semaine : S46 rognée (202) puis S47 rognée (7)."""
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"),
        {"debut": "2026-11-10", "fin": "2026-11-18", "granularite": "semaine"},
    )
    assert data["granularite"] == "semaine"
    assert _bornes(data) == [
        ("2026-11-10", "2026-11-13", "S46"),
        ("2026-11-14", "2026-11-18", "S47"),
    ]
    _point(data["points"][0], 1, 1.0, 0.8, {"incident": 1})  # 202 le 13/11 à 23 h
    # 101, 108, 102, 103, 104, 109, 105
    _point(data["points"][1], 7, (130 + 30 + 60 + 255) / 60, 2.6 + 0.5 + 4.0 + 1.05,
           {"incident": 3, "autre": 2, "delestage": 1, "travaux": 1})


async def test_semaine_auto_sur_51_jours(client_suivi: AsyncClient) -> None:
    """01/10 → 20/11 (51 jours) → semaine ; S40 rognée, S43 et S44 vides présentes."""
    params = {"debut": "2026-10-01", "fin": "2026-11-20"}
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), params)
    assert data["granularite"] == "semaine"
    assert [p["libelle"] for p in data["points"]] == ["S40", "S41", "S42", "S43", "S44", "S45", "S46", "S47"]
    assert (data["points"][0]["debut"], data["points"][0]["fin"]) == ("2026-10-01", "2026-10-02")
    assert (data["points"][-1]["debut"], data["points"][-1]["fin"]) == ("2026-11-14", "2026-11-20")
    assert _nombres(data) == [0, 1, 2, 0, 0, 1, 2, 9]
    _point(data["points"][1], 1, 1.0, 0.3, {"incident": 1})  # 304
    _point(data["points"][2], 2, 40 / 60, 0.5, {"incident": 2})  # 305, 306
    _point(data["points"][5], 1, 100 / 60, 1.0, {"incident": 1})  # 205 (06/11 à 23 h 59)
    _point(data["points"][6], 2, 80 / 60, 0.9, {"incident": 2})  # 204, 202
    _point(data["points"][7], 9, 610 / 60, 9.85, {"incident": 4, "delestage": 1, "travaux": 1, "autre": 3})
    assert sum(_nombres(data)) == await _kpi_nombre(client_suivi, _make_user("ADMIN_SAQS"), params) == 15


async def test_semaines_changement_d_annee_s53_s1(client_suivi: AsyncClient) -> None:
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"),
        {"debut": "2026-12-26", "fin": "2027-01-08", "granularite": "semaine"},
    )
    assert _bornes(data) == [
        ("2026-12-26", "2027-01-01", "S53"),
        ("2027-01-02", "2027-01-08", "S1"),
    ]
    _point(data["points"][0], 1, 0.75, 0.9, {"autre": 1})  # 307 (cause HTB)
    _point(data["points"][1], 2, 35 / 60, 0.55, {"delestage": 1, "autre": 1})  # 308, 309


# --------------------------------------------------------------------------------------------
# Granularité mois
# --------------------------------------------------------------------------------------------


async def test_mois_auto_au_dela_de_186_jours(client_suivi: AsyncClient) -> None:
    """01/07/2026 → 05/01/2027 (189 jours) → mois ; juillet vide, janvier rogné."""
    params = {"debut": "2026-07-01", "fin": "2027-01-05"}
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), params)
    assert data["granularite"] == "mois"
    assert _bornes(data) == [
        ("2026-07-01", "2026-07-31", "juil. 2026"),
        ("2026-08-01", "2026-08-31", "août 2026"),
        ("2026-09-01", "2026-09-30", "sept. 2026"),
        ("2026-10-01", "2026-10-31", "oct. 2026"),
        ("2026-11-01", "2026-11-30", "nov. 2026"),
        ("2026-12-01", "2026-12-31", "déc. 2026"),
        ("2027-01-01", "2027-01-05", "janv. 2027"),
    ]
    assert _nombres(data) == [0, 2, 1, 3, 13, 1, 1]
    juil, aout, sept, octo, nov, dec, janv = data["points"]
    _point(juil, 0, 0.0, 0.0, {})
    _point(aout, 2, 1.5, 0.7, {"incident": 1, "delestage": 1})  # 301, 302 (31/08 à 23 h 30)
    _point(sept, 1, 2.0, 0.6, {"travaux": 1})  # 303 (01/09 à 0 h)
    _point(octo, 3, 100 / 60, 0.8, {"incident": 3})  # 304, 305, 306
    # S47 (9) + 202, 203, 204, 205
    _point(nov, 13, (610 + 60 + 100 + 20 + 100) / 60, 9.85 + 0.8 + 1.0 + 0.1 + 1.0,
           {"incident": 8, "delestage": 1, "travaux": 1, "autre": 3})
    _point(dec, 1, 0.75, 0.9, {"autre": 1})  # 307
    _point(janv, 1, 20 / 60, 0.5, {"delestage": 1})  # 308 ; 309 (08/01) hors période
    assert sum(_nombres(data)) == await _kpi_nombre(client_suivi, _make_user("ADMIN_SAQS"), params) == 21


async def test_mois_force_rogne(client_suivi: AsyncClient) -> None:
    """15/08 → 20/11, mois : août rogné (301 du 10/08 exclue), novembre rogné au 20 (203 exclue)."""
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"),
        {"debut": "2026-08-15", "fin": "2026-11-20", "granularite": "mois"},
    )
    assert data["granularite"] == "mois"
    assert _bornes(data) == [
        ("2026-08-15", "2026-08-31", "août 2026"),
        ("2026-09-01", "2026-09-30", "sept. 2026"),
        ("2026-10-01", "2026-10-31", "oct. 2026"),
        ("2026-11-01", "2026-11-20", "nov. 2026"),
    ]
    assert _nombres(data) == [1, 1, 3, 12]


async def test_mois_sur_trois_ans(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"debut": "2024-01-01", "fin": "2026-12-31"})
    assert data["granularite"] == "mois"
    assert len(data["points"]) == 36
    assert data["points"][0]["libelle"] == "janv. 2024"
    assert data["points"][-1]["libelle"] == "déc. 2026"
    assert data["points"][26]["libelle"] == "mars 2026"
    assert data["points"][26]["nombre"] == 12  # 310 à 321


# --------------------------------------------------------------------------------------------
# Jour forcé : limite de 366 jours
# --------------------------------------------------------------------------------------------


async def test_jour_force_366_jours_accepte(client_suivi: AsyncClient) -> None:
    params = {"debut": "2026-01-01", "fin": "2027-01-01", "granularite": "jour"}
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), params)
    assert data["granularite"] == "jour"
    assert len(data["points"]) == 366
    assert data["points"][0]["libelle"] == "01/01"
    mars_10 = next(p for p in data["points"] if p["debut"] == "2026-03-10")
    assert mars_10["nombre"] == 12
    assert sum(_nombres(data)) == await _kpi_nombre(client_suivi, _make_user("ADMIN_SAQS"), params)


async def test_jour_force_plus_de_366_jours_422(client_suivi: AsyncClient) -> None:
    response = await appeler(
        client_suivi, URL, _make_user("ADMIN_SAQS"),
        {"debut": "2025-01-01", "fin": "2026-01-02", "granularite": "jour"},
    )
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


@pytest.mark.parametrize("granularite", ["semaine", "mois"])
async def test_semaine_et_mois_plus_de_366_jours_acceptes(client_suivi: AsyncClient, granularite: str) -> None:
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"),
        {"debut": "2025-01-01", "fin": "2026-01-02", "granularite": granularite},
    )
    assert data["granularite"] == granularite


# --------------------------------------------------------------------------------------------
# Cohérence avec la Vue d'ensemble, filtres
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"reseau": "htb"},
        {"reseau": "hta"},
        {"exogene": "true"},
        {"poste_source_id": 1},
        {"region_id": 2},
        {"debut": "2026-10-01", "fin": "2026-11-20"},
        {"debut": "2026-07-01", "fin": "2027-01-05", "reseau": "htb"},
    ],
)
async def test_somme_des_points_egale_kpi_vue_ensemble(client_suivi: AsyncClient, params: dict[str, Any]) -> None:
    user = _make_user("ADMIN_SAQS")
    data = await _ok(client_suivi, user, params)
    assert sum(_nombres(data)) == await _kpi_nombre(client_suivi, user, params)


async def test_filtre_reseau_htb(client_suivi: AsyncClient) -> None:
    """reseau=htb : 103 (16/11, délestage) et 106 (19/11, autre) ; les autres jours à 0."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"reseau": "htb"})
    assert _nombres(data) == [0, 0, 1, 0, 0, 1, 0]
    assert _natures(data["points"][2]) == {"delestage": 1}
    assert _natures(data["points"][5]) == {"autre": 1}


async def test_filtre_poste_source(client_suivi: AsyncClient) -> None:
    """poste_source_id=1 : 101 (14/11), 102 (15/11), 107 (20/11)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"poste_source_id": 1})
    assert _nombres(data) == [1, 1, 0, 0, 0, 0, 1]


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"granularite": "annee"},
        {"granularite": "trimestre"},
        {"granularite": "heure"},
        {"debut": "2026-11-20", "fin": "2026-11-14"},
        {"debut": "2020-01-01", "fin": "2026-11-20"},
        {"reseau": "bt"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_suivi: AsyncClient, params: dict[str, Any]) -> None:
    response = await appeler(client_suivi, URL, _make_user("ADMIN_SAQS"), {**SEMAINE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


# --------------------------------------------------------------------------------------------
# Authentification et périmètre
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client_suivi: AsyncClient) -> None:
    response = await client_suivi.get(URL, params=SEMAINE)
    assert response.status_code in (401, 403)


async def test_jeton_invalide_401(client_suivi: AsyncClient) -> None:
    response = await client_suivi.get(URL, params=SEMAINE, headers={"Authorization": "Bearer pas-un-jwt"})
    assert response.status_code == 401


async def test_sans_permission_indicateurs_read_403(client_suivi: AsyncClient) -> None:
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await appeler(client_suivi, URL, user, SEMAINE)
    assert response.status_code == 403


async def test_role_hors_regle_des_indicateurs_403(client_suivi: AsyncClient) -> None:
    response = await appeler(client_suivi, URL, _make_user("DISPATCHER"), SEMAINE)
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national(client_suivi: AsyncClient, role: str) -> None:
    data = await _ok(client_suivi, _make_user(role))
    assert sum(_nombres(data)) == 9


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_suivi: AsyncClient, role: str) -> None:
    """Région 2 : 104 et 109 (17/11), 105 (18/11)."""
    data = await _ok(client_suivi, _make_user(role, scope_service_id=2))
    assert _nombres(data) == [0, 0, 0, 2, 1, 0, 0]
    assert _natures(data["points"][3]) == {"travaux": 1, "incident": 1}


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_suivi: AsyncClient, role: str) -> None:
    response = await appeler(
        client_suivi, URL, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 1}
    )
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("BCC", scope_service_id=2), {"service_id": 1})
    assert sum(_nombres(data)) == 0
    assert len(data["points"]) == 7


async def test_superviseur_limite_a_son_service(client_suivi: AsyncClient) -> None:
    """SDDV : 101 (14/11), 102 (15/11), 107 (20/11)."""
    data = await _ok(client_suivi, _make_user("SUPERVISEUR", scope_service_id=1))
    assert _nombres(data) == [1, 1, 0, 0, 0, 0, 1]


async def test_superviseur_autre_service_403(client_suivi: AsyncClient) -> None:
    response = await appeler(
        client_suivi, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**SEMAINE, "service_id": 2}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_redis_cle_suivi_evolution(client_suivi: AsyncClient, fake_redis: Any) -> None:
    await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    cles = [c async for c in fake_redis.scan_iter("suivi:evolution:*")]
    assert cles, "aucune clé suivi:evolution:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_cache_par_granularite_et_perimetre(client_suivi: AsyncClient) -> None:
    """La granularité et le périmètre font partie de la clé."""
    jours = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"granularite": "jour"})
    semaine = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"granularite": "semaine"})
    bcc = await _ok(client_suivi, _make_user("BCC", scope_service_id=2), {"granularite": "semaine"})
    assert len(jours["points"]) == 7
    assert semaine["granularite"] == "semaine"
    assert _bornes(semaine) == [("2026-11-14", "2026-11-20", "S47")]
    assert _nombres(semaine) == [9]
    assert _nombres(bcc) == [3]
