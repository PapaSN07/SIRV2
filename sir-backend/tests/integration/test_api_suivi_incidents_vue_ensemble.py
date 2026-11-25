"""GET /api/v1/suivi-incidents/vue-ensemble — onglet Vue d'ensemble (spécification étape 3, §8).

Interruptions distribution, tous statuts, datées par l'apparition sur [debut, fin] (fin incluse),
filtres résolus (``resoudre_filtres``) appliqués par ``appliquer_filtres``. Réponse
``ApiResponse[VueEnsemble]`` : filtres, periode_precedente, kpi, kpi_precedent, natures, reseaux.

Données : ``tests/integration/_donnees_suivi_incidents.py`` (SQLite, tableau des interruptions).
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

URL = "/api/v1/suivi-incidents/vue-ensemble"
APPROX = {"abs": 0.01}


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **(params or {})})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    return corps["data"]


def _kpi(
    data: dict[str, Any],
    cle: str,
    nombre: int,
    duree_h: float,
    moyenne_min: float | None,
    postes: int,
    clients: int,
    end: float,
) -> None:
    kpi = data[cle]
    assert kpi["nombre_interruptions"] == nombre
    assert kpi["duree_totale_heures"] == pytest.approx(duree_h, **APPROX)
    if moyenne_min is None:
        assert kpi["duree_moyenne_minutes"] is None
    else:
        assert kpi["duree_moyenne_minutes"] == pytest.approx(moyenne_min, **APPROX)
    assert kpi["postes_touches"] == postes
    assert kpi["coupures_clients"] == clients
    assert kpi["end_mwh"] == pytest.approx(end, **APPROX)


def _par_cle(lignes: list[dict[str, Any]], cle: str) -> dict[str, dict[str, Any]]:
    return {ligne[cle]: ligne for ligne in lignes}


# --------------------------------------------------------------------------------------------
# Authentification, droits, validation
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client_suivi: AsyncClient) -> None:
    """Sans jeton : refusé (HTTPBearer de l'application : 403 ; 401 accepté), jamais 404."""
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
    """DISPATCHER avec indicateurs:read : rôle transport → 403 (même règle que /filtres)."""
    response = await appeler(client_suivi, URL, _make_user("DISPATCHER"), SEMAINE)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "params",
    [
        {"debut": "2026-11-20", "fin": "2026-11-14"},  # fin avant début
        {"debut": "2020-01-01", "fin": "2026-11-20"},  # plus de trois ans
        {"reseau": "bt"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_suivi: AsyncClient, params: dict[str, Any]) -> None:
    """Période ou réseau invalide → 422 enveloppé {"status": "error", "data": null, "error": "..."}."""
    response = await appeler(client_suivi, URL, _make_user("ADMIN_SAQS"), {**SEMAINE, **params})
    assert response.status_code == 422
    erreur_enveloppee(response.json())


# --------------------------------------------------------------------------------------------
# KPI, période précédente
# --------------------------------------------------------------------------------------------


async def test_kpi_national(client_suivi: AsyncClient) -> None:
    """S47 national : 9 interruptions distribution (tous statuts), transport et hors période exclus.

    Durées 120+30+60+240+90+45+10+15 = 610 min (105 sans durée compte 0) ; moyenne sur les 8
    durées renseignées = 76,25 min ; postes distincts P1..P5 = 5 (P2, P4 partagés) ;
    coupures-clients 4 770 (une interruption à plusieurs postes n'est comptée qu'une fois) ;
    END 9,85 MWh.
    """
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    _kpi(data, "kpi", 9, 610 / 60, 76.25, 5, 4770, 9.85)


async def test_kpi_precedent_et_periode_precedente(client_suivi: AsyncClient) -> None:
    """S46 (07/11 → 13/11) avec les mêmes filtres : 202 et 204 ; 205 (06/11) exclue."""
    from app.services.suivi_incidents_service import libelle_periode
    from datetime import date

    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    assert data["periode_precedente"] == {
        "debut": "2026-11-07",
        "fin": "2026-11-13",
        "libelle": libelle_periode(date(2026, 11, 7), date(2026, 11, 13)),
    }
    assert data["periode_precedente"]["libelle"] == "S46 · 07/11 → 13/11/2026"
    _kpi(data, "kpi_precedent", 2, 80 / 60, 40.0, 1, 500, 0.9)


async def test_filtres_resolus_renvoyes(client_suivi: AsyncClient) -> None:
    """``filtres`` = FiltresResolus, comme GET /suivi-incidents/filtres."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"poste_source_id": 1})
    resolus = data["filtres"]
    assert resolus["filtres"]["debut"] == "2026-11-14"
    assert resolus["filtres"]["fin"] == "2026-11-20"
    assert resolus["filtres"]["poste_source_id"] == 1
    assert resolus["semaine"] == {"numero": 47, "annee": 2026, "debut": "2026-11-14", "fin": "2026-11-20"}
    assert resolus["libelle_periode"] == "S47 · 14/11 → 20/11/2026"
    assert resolus["perimetre"]["niveau"] == "national"


async def test_periode_libre_precedente_meme_duree(client_suivi: AsyncClient) -> None:
    """Période libre 17/11 → 20/11 (4 jours) : précédente 13/11 → 16/11 (202, 101, 102, 103, 108)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"debut": "2026-11-17", "fin": "2026-11-20"})
    assert (data["periode_precedente"]["debut"], data["periode_precedente"]["fin"]) == ("2026-11-13", "2026-11-16")
    # période : 104, 105, 106, 107, 109
    _kpi(data, "kpi", 5, (240 + 90 + 45 + 15) / 60, 97.5, 3, 1220, 2.75)
    # précédente : 202, 108, 101, 102, 103
    _kpi(data, "kpi_precedent", 5, (60 + 10 + 120 + 30 + 60) / 60, 56.0, 4, 3950, 7.9)


async def test_duree_moyenne_nulle_sans_duree_renseignee(client_suivi: AsyncClient) -> None:
    """Seule l'interruption 105 (en cours, sans durée, clients ni END) : moyenne null, sommes à 0."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"cause_id": 5})
    _kpi(data, "kpi", 1, 0.0, None, 0, 0, 0.0)


async def test_aucune_interruption(client_suivi: AsyncClient) -> None:
    """Période vide : KPI à 0, moyenne null, 4 natures à 0 (part 0), réseaux à 0."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"debut": "2026-12-05", "fin": "2026-12-11"})
    _kpi(data, "kpi", 0, 0.0, None, 0, 0, 0.0)
    assert [n["categorie"] for n in data["natures"]] == ["incident", "delestage", "travaux", "autre"]
    for ligne in data["natures"]:
        assert ligne["nombre"] == 0
        assert ligne["part"] == 0
        assert ligne["duree_heures"] == pytest.approx(0.0)
        assert ligne["end_mwh"] == pytest.approx(0.0)
    assert [r["reseau"] for r in data["reseaux"]] == ["hta", "htb", "total"]
    assert all(r["nombre"] == 0 for r in data["reseaux"])


# --------------------------------------------------------------------------------------------
# Natures et réseaux
# --------------------------------------------------------------------------------------------


async def test_natures_quatre_lignes_dans_l_ordre(client_suivi: AsyncClient) -> None:
    """incident (101, 102, 107, 109), delestage (103), travaux (104), autre (105, 106, 108)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    natures = data["natures"]
    assert [n["categorie"] for n in natures] == ["incident", "delestage", "travaux", "autre"]
    assert [n["libelle"] for n in natures] == ["Incidents", "Délestages", "Travaux", "Autres coupures"]
    attendus = {
        "incident": (4, 210 / 60, 3.25),
        "delestage": (1, 1.0, 4.0),
        "travaux": (1, 4.0, 1.0),
        "autre": (3, 100 / 60, 1.6),
    }
    for ligne in natures:
        nombre, duree, end = attendus[ligne["categorie"]]
        assert ligne["nombre"] == nombre, ligne
        assert ligne["duree_heures"] == pytest.approx(duree, **APPROX), ligne
        assert ligne["end_mwh"] == pytest.approx(end, **APPROX), ligne
        assert ligne["part"] == pytest.approx(nombre / 9, abs=1e-3), ligne
    assert sum(n["nombre"] for n in natures) == data["kpi"]["nombre_interruptions"]
    assert sum(n["part"] for n in natures) == pytest.approx(1.0, abs=1e-3)


async def test_reseaux_hta_htb_total(client_suivi: AsyncClient) -> None:
    """HTB = cause HTB / PRODUCTION (103, 106) ; HTA = les autres, y compris sans cause ; total = somme."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    reseaux = data["reseaux"]
    assert [r["reseau"] for r in reseaux] == ["hta", "htb", "total"]
    par = _par_cle(reseaux, "reseau")
    assert par["htb"]["nombre"] == 2
    assert par["htb"]["duree_heures"] == pytest.approx(2.5, **APPROX)
    assert par["htb"]["end_mwh"] == pytest.approx(5.5, **APPROX)
    assert par["hta"]["nombre"] == 7
    assert par["hta"]["duree_heures"] == pytest.approx(460 / 60, **APPROX)
    assert par["hta"]["end_mwh"] == pytest.approx(4.35, **APPROX)
    for champ in ("nombre", "duree_heures", "end_mwh"):
        assert par["total"][champ] == pytest.approx(par["hta"][champ] + par["htb"][champ], **APPROX)
    assert par["total"]["nombre"] == data["kpi"]["nombre_interruptions"]
    assert par["total"]["end_mwh"] == pytest.approx(data["kpi"]["end_mwh"], **APPROX)
    assert par["total"]["duree_heures"] == pytest.approx(data["kpi"]["duree_totale_heures"], **APPROX)


# --------------------------------------------------------------------------------------------
# Filtres appliqués
# --------------------------------------------------------------------------------------------


async def test_filtre_poste_source(client_suivi: AsyncClient) -> None:
    """poste_source_id=1 : 101, 102, 107 ; précédente : 202."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"poste_source_id": 1})
    _kpi(data, "kpi", 3, 195 / 60, 65.0, 3, 1600, 3.2)
    _kpi(data, "kpi_precedent", 1, 1.0, 60.0, 1, 400, 0.8)
    natures = _par_cle(data["natures"], "categorie")
    assert natures["incident"]["nombre"] == 3
    assert natures["incident"]["part"] == pytest.approx(1.0)
    assert natures["autre"]["nombre"] == 0


async def test_filtre_reseau_htb(client_suivi: AsyncClient) -> None:
    """reseau=htb : 103 (délestage production) et 106 (autre HTB)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"reseau": "htb"})
    _kpi(data, "kpi", 2, 2.5, 75.0, 1, 2800, 5.5)
    reseaux = _par_cle(data["reseaux"], "reseau")
    assert (reseaux["hta"]["nombre"], reseaux["htb"]["nombre"], reseaux["total"]["nombre"]) == (0, 2, 2)
    natures = _par_cle(data["natures"], "categorie")
    assert natures["delestage"]["nombre"] == 1
    assert natures["autre"]["nombre"] == 1
    assert natures["incident"]["nombre"] == 0
    # précédente : aucune interruption HTB
    assert data["kpi_precedent"]["nombre_interruptions"] == 0


async def test_filtre_reseau_hta(client_suivi: AsyncClient) -> None:
    """reseau=hta : les 7 autres, dont 107 et 108 sans cause."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"reseau": "hta"})
    assert data["kpi"]["nombre_interruptions"] == 7
    assert data["kpi_precedent"]["nombre_interruptions"] == 2


@pytest.mark.parametrize(("exogene", "nombre"), [("true", 1), ("false", 8)])
async def test_filtre_exogene(client_suivi: AsyncClient, exogene: str, nombre: int) -> None:
    """exogene=true : 102 (choc accidentel) ; false : les 8 autres (sans cause comprises)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"exogene": exogene})
    assert data["kpi"]["nombre_interruptions"] == nombre


async def test_filtre_nature_et_service(client_suivi: AsyncClient) -> None:
    """service_id=1 et nature_id=1 (PERMANENT) : 101 seule ; précédente : 202."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"service_id": 1, "nature_id": 1})
    _kpi(data, "kpi", 1, 2.0, 120.0, 2, 1000, 2.5)
    assert data["kpi_precedent"]["nombre_interruptions"] == 1


# --------------------------------------------------------------------------------------------
# Périmètre (RBAC double : require_permission + WHERE)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national_toutes_regions(client_suivi: AsyncClient, role: str) -> None:
    data = await _ok(client_suivi, _make_user(role))
    assert data["kpi"]["nombre_interruptions"] == 9
    assert data["filtres"]["perimetre"]["niveau"] == "national"


async def test_role_national_choisit_une_region(client_suivi: AsyncClient) -> None:
    """ADMIN_SAQS region_id=2 : 104, 105, 109 ; précédente : 204."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"region_id": 2})
    _kpi(data, "kpi", 3, 255 / 60, 127.5, 1, 320, 1.05)
    _kpi(data, "kpi_precedent", 1, 20 / 60, 20.0, 0, 100, 0.1)


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_suivi: AsyncClient, role: str) -> None:
    """BCC / BRC de la région 2 sans filtre : seulement les interruptions de sa région (WHERE)."""
    data = await _ok(client_suivi, _make_user(role, scope_service_id=2))
    _kpi(data, "kpi", 3, 255 / 60, 127.5, 1, 320, 1.05)
    _kpi(data, "kpi_precedent", 1, 20 / 60, 20.0, 0, 100, 0.1)
    assert data["filtres"]["filtres"]["region_id"] == 2
    assert data["filtres"]["perimetre"]["region_verrouillee"] is True
    reseaux = _par_cle(data["reseaux"], "reseau")
    assert reseaux["total"]["nombre"] == 3
    assert sum(n["nombre"] for n in data["natures"]) == 3


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_suivi: AsyncClient, role: str) -> None:
    """BCC / BRC qui demande une autre région → 403 (règle de resoudre_filtres / _resolve_scope)."""
    response = await appeler(
        client_suivi, URL, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 1}
    )
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_suivi: AsyncClient) -> None:
    """BCC région 2 qui filtre sur SDDV (Dakar) : la région reste imposée → aucune interruption."""
    data = await _ok(client_suivi, _make_user("BCC", scope_service_id=2), {"service_id": 1})
    _kpi(data, "kpi", 0, 0.0, None, 0, 0, 0.0)
    assert data["kpi_precedent"]["nombre_interruptions"] == 0


async def test_superviseur_limite_a_son_service(client_suivi: AsyncClient) -> None:
    """SUPERVISEUR du service 1 : 101, 102, 107 ; précédente : 202."""
    data = await _ok(client_suivi, _make_user("SUPERVISEUR", scope_service_id=1))
    _kpi(data, "kpi", 3, 195 / 60, 65.0, 3, 1600, 3.2)
    _kpi(data, "kpi_precedent", 1, 1.0, 60.0, 1, 400, 0.8)
    assert data["filtres"]["perimetre"]["service_verrouille"] is True


async def test_superviseur_autre_service_403(client_suivi: AsyncClient) -> None:
    response = await appeler(
        client_suivi, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**SEMAINE, "service_id": 2}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_redis_cle_suivi_ttl_une_heure(client_suivi: AsyncClient, fake_redis: Any) -> None:
    """Résultat mis en cache sous ``suivi:{endpoint}:{empreinte}``, TTL ≤ 1 h."""
    await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    cles = [c async for c in fake_redis.scan_iter("suivi:*")]
    assert cles, "aucune clé suivi:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_cache_par_filtres_resolus(client_suivi: AsyncClient) -> None:
    """Mêmes paramètres, périmètres différents : le résultat du BCC n'est pas servi au national."""
    bcc = await _ok(client_suivi, _make_user("BCC", scope_service_id=2))
    national = await _ok(client_suivi, _make_user("ADMIN_SAQS"))
    bcc_bis = await _ok(client_suivi, _make_user("BCC", scope_service_id=2))
    assert bcc["kpi"]["nombre_interruptions"] == 3
    assert national["kpi"]["nombre_interruptions"] == 9
    assert bcc_bis["kpi"] == bcc["kpi"]
