"""GET /api/v1/suivi-incidents/carte — onglet Carte (spécification étape 6a, §11).

Mêmes règles que les étapes 3 à 5 : interruptions distribution, tous statuts, filtres résolus
appliqués par ``appliquer_filtres`` (RBAC double), 422 enveloppés, cache Redis 1 h
``suivi:carte:{empreinte}``.

Réponse ``ApiResponse[CarteSuivi]`` : ``postes_touches``, ``postes_localises``, ``tronque``, ``points``.
Un point par poste **localisé** :
``{poste_id, code, libelle, feeder_id, feeder, nombre, duree_heures, clients, nature_dominante,
longitude, latitude, localisation}`` (``feeder_id`` ajouté par le coordinateur le 25/11/2026).

Localisation : 1. ``rapprochement`` (ligne schema_unifilaire_postes auto / manuel, nœud actif dans
l'emprise, plus petite id) ; 2. ``nom`` (``coords_par_nom`` sur le libellé puis le code,
``choisir_point`` avec le feeder **du poste**) ; 3. sinon non localisé.

Au plus ``suivi_incidents_service.LIMITE_POINTS_CARTE`` = 3 000 points (nombre décroissant puis
libellé) ; ``tronque`` = des postes localisés ont été écartés ; ``postes_localises`` compte tous les
postes localisés (avant la limite).

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
    POINT_ALPHA,
    POINT_BRAVO,
    POINT_CHARLIE,
    POINT_ECHO,
    POINT_FOXTROT,
    POINT_HOTEL,
    POINT_INDIA,
    SEMAINE,
    _make_user,
    appeler,
    client_carte,
    erreur_enveloppee,
    session_carte,
)

pytestmark = pytest.mark.asyncio

URL = "/api/v1/suivi-incidents/carte"
CHAMPS_REPONSE = {"postes_touches", "postes_localises", "tronque", "points"}
CHAMPS_POINT = {
    "poste_id", "code", "libelle", "feeder_id", "feeder", "nombre", "duree_heures", "clients",
    "nature_dominante", "longitude", "latitude", "localisation",
}
COORD = {"abs": 1e-6}

# Ordre attendu en national sur S47 : nombre décroissant puis libellé
ORDRE_NATIONAL = ["ALPHA", "CHARLIE", "ECHO", "FOXTROT", "HOTEL", "BRAVO", "INDIA"]


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **(params or {})})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    data = corps["data"]
    assert set(data) == CHAMPS_REPONSE, data
    for point in data["points"]:
        assert set(point) == CHAMPS_POINT, point
    return data


def _par_libelle(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["libelle"]: p for p in data["points"]}


def _coords(point: dict[str, Any], attendu: tuple[float, float], tolerance: float = 1e-6) -> None:
    assert point["longitude"] == pytest.approx(attendu[0], abs=tolerance), point
    assert point["latitude"] == pytest.approx(attendu[1], abs=tolerance), point


def _nationale() -> Any:
    return _make_user("ADMIN_SAQS")


# --------------------------------------------------------------------------------------------
# Postes touchés et localisés
# --------------------------------------------------------------------------------------------


async def test_postes_touches_et_localises(client_carte: AsyncClient) -> None:
    """13 postes touchés en S47 (transport 620, 621 du 21/11 et 622 du 13/11 exclus), 7 localisés."""
    data = await _ok(client_carte, _nationale())
    assert data["postes_touches"] == 13
    assert data["postes_localises"] == 7
    assert data["tronque"] is False
    assert len(data["points"]) == 7


async def test_seuls_les_postes_localises_ont_un_point(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale())
    assert set(_par_libelle(data)) == {"ALPHA", "BRAVO", "CHARLIE", "ECHO", "FOXTROT", "HOTEL", "INDIA"}
    for point in data["points"]:
        assert point["longitude"] is not None and point["latitude"] is not None


async def test_tri_nombre_decroissant_puis_libelle(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale())
    assert [p["libelle"] for p in data["points"]] == ORDRE_NATIONAL


async def test_champs_exacts_d_un_point(client_carte: AsyncClient) -> None:
    """ALPHA : feeder du poste, 3 interruptions (601, 602, 603), 90 min (603 en cours sans durée),
    clients 100 + 50 + 0 (estimés), incident dominant, localisé par le rapprochement."""
    alpha = _par_libelle(await _ok(client_carte, _nationale()))["ALPHA"]
    assert alpha["poste_id"] == 1
    assert alpha["code"] == "P-ALPHA"
    assert alpha["feeder_id"] == 1
    assert alpha["feeder"] == "HANN DEPART 1"
    assert alpha["nombre"] == 3
    assert alpha["duree_heures"] == pytest.approx(1.5, abs=0.01)
    assert alpha["clients"] == 150
    assert alpha["nature_dominante"] == "incident"
    assert alpha["localisation"] == "rapprochement"
    _coords(alpha, POINT_ALPHA)


async def test_valeurs_de_tous_les_points(client_carte: AsyncClient) -> None:
    points = _par_libelle(await _ok(client_carte, _nationale()))
    attendus = {
        # libellé: (poste_id, code, feeder_id, feeder, nombre, durée h, clients, nature, localisation)
        "ALPHA": (1, "P-ALPHA", 1, "HANN DEPART 1", 3, 1.5, 150, "incident", "rapprochement"),
        "BRAVO": (2, "P-BRAVO", 1, "HANN DEPART 1", 1, 1.0, 200, "incident", "rapprochement"),
        "CHARLIE": (3, "P-CHARLIE", 2, "HANN DEPART 2", 2, 55 / 60, 70, "delestage", "nom"),
        "ECHO": (5, "P-ECHO", 3, "BEL AIR 2", 2, 2.75, 30, "travaux", "nom"),
        "FOXTROT": (6, "P-FOX", 4, "KAOLACK VILLE", 2, 1.75, 600, "incident", "nom"),
        "HOTEL": (8, "P-HOTEL", None, None, 2, 0.5, 10, "incident", "nom"),
        "INDIA": (9, "P-INDIA9", 5, "DEPART ISOLE", 1, 10 / 60, 7, "incident", "nom"),
    }
    for libelle, (pid, code, fid, feeder, nombre, heures, clients, nature, mode) in attendus.items():
        p = points[libelle]
        assert (p["poste_id"], p["code"], p["feeder_id"], p["feeder"]) == (pid, code, fid, feeder), p
        assert p["nombre"] == nombre, p
        assert p["duree_heures"] == pytest.approx(heures, abs=0.01), p
        assert p["clients"] == clients, p
        assert p["nature_dominante"] == nature, p
        assert p["localisation"] == mode, p


# --------------------------------------------------------------------------------------------
# Règle de localisation
# --------------------------------------------------------------------------------------------


async def test_rapprochement_prioritaire_sur_le_nom(client_carte: AsyncClient) -> None:
    """ALPHA a aussi un nœud SIG « ALPHA » (-17.10, 14.60) : le nœud rapproché (-17.40, 14.70) gagne."""
    alpha = _par_libelle(await _ok(client_carte, _nationale()))["ALPHA"]
    assert alpha["localisation"] == "rapprochement"
    _coords(alpha, POINT_ALPHA)
    assert alpha["longitude"] != pytest.approx(-17.10, abs=1e-3)


async def test_rapprochement_ambigu_ignore_meme_avec_la_plus_petite_id(client_carte: AsyncClient) -> None:
    """ALPHA : ligne 1 « ambigu » (nœud -16.00, 13.00) ignorée au profit de la ligne 4 « auto »."""
    alpha = _par_libelle(await _ok(client_carte, _nationale()))["ALPHA"]
    assert alpha["longitude"] != pytest.approx(-16.00, abs=1e-3)
    _coords(alpha, POINT_ALPHA)


async def test_rapprochement_manuel_plus_petite_id_et_conversion_utm(client_carte: AsyncClient) -> None:
    """BRAVO : lignes 2 (manuel, nœud en UTM 28N) et 5 (auto) → la ligne 2, convertie en degrés."""
    bravo = _par_libelle(await _ok(client_carte, _nationale()))["BRAVO"]
    assert bravo["localisation"] == "rapprochement"
    _coords(bravo, POINT_BRAVO)


async def test_seul_rapprochement_ambigu_retombe_sur_le_nom(client_carte: AsyncClient) -> None:
    """CHARLIE : seule ligne « ambigu » → nœud « CHARLIE » trouvé par le nom."""
    charlie = _par_libelle(await _ok(client_carte, _nationale()))["CHARLIE"]
    assert charlie["localisation"] == "nom"
    _coords(charlie, POINT_CHARLIE)


async def test_noeud_rapproche_inactif_ignore(client_carte: AsyncClient) -> None:
    """DELTA : nœud rapproché inactif (et seul nœud « DELTA », inactif) → non localisé."""
    data = await _ok(client_carte, _nationale())
    assert "DELTA" not in _par_libelle(data)


async def test_noeud_rapproche_hors_emprise_ignore(client_carte: AsyncClient) -> None:
    """ECHO : nœud rapproché en (0, 0), hors du Sénégal → nœud « ECHO » trouvé par le nom."""
    echo = _par_libelle(await _ok(client_carte, _nationale()))["ECHO"]
    assert echo["localisation"] == "nom"
    _coords(echo, POINT_ECHO)


async def test_homonymes_departages_par_le_feeder_du_poste(client_carte: AsyncClient) -> None:
    """FOXTROT (feeder 4) : nœuds « FOXTROT » sur F4 et F1, éloignés → celui de F4."""
    foxtrot = _par_libelle(await _ok(client_carte, _nationale()))["FOXTROT"]
    assert foxtrot["localisation"] == "nom"
    _coords(foxtrot, POINT_FOXTROT)


async def test_libelle_avant_le_code(client_carte: AsyncClient) -> None:
    """FOXTROT : un nœud porte aussi son code « P-FOX » (-15.50, 13.50) ; le libellé passe d'abord."""
    foxtrot = _par_libelle(await _ok(client_carte, _nationale()))["FOXTROT"]
    assert foxtrot["longitude"] != pytest.approx(-15.50, abs=1e-3)


async def test_homonymes_eloignes_sans_feeder_non_localise(client_carte: AsyncClient) -> None:
    """GOLF (sans feeder) : homonymes éloignés → non localisé ; MIKE (F4) : homonymes sur F1 et F3."""
    points = _par_libelle(await _ok(client_carte, _nationale()))
    assert "GOLF" not in points
    assert "MIKE" not in points


async def test_homonymes_proches_localises(client_carte: AsyncClient) -> None:
    """HOTEL (sans feeder) : deux nœuds à moins de 0,01° → placé."""
    hotel = _par_libelle(await _ok(client_carte, _nationale()))["HOTEL"]
    assert hotel["localisation"] == "nom"
    _coords(hotel, POINT_HOTEL, tolerance=1e-3)


async def test_code_du_poste_si_le_libelle_ne_trouve_rien(client_carte: AsyncClient) -> None:
    """INDIA : aucun nœud « INDIA », nœud « P-INDIA9 » (son code)."""
    india = _par_libelle(await _ok(client_carte, _nationale()))["INDIA"]
    assert india["localisation"] == "nom"
    _coords(india, POINT_INDIA)


async def test_noeuds_inactifs_hors_emprise_ou_sans_coordonnees_non_localises(client_carte: AsyncClient) -> None:
    """JULIET (nœud inactif), KILO (sans nœud rapproché, nœud « KILO » hors emprise), LIMA (nœud
    rapproché sans coordonnées)."""
    points = _par_libelle(await _ok(client_carte, _nationale()))
    for libelle in ("JULIET", "KILO", "LIMA"):
        assert libelle not in points


# --------------------------------------------------------------------------------------------
# Sommes par poste et nature dominante
# --------------------------------------------------------------------------------------------


async def test_pas_de_double_comptage(client_carte: AsyncClient) -> None:
    """Σ nombre des points = lignes poste_interruptions des postes localisés (pas de produit par
    nature, nœud ou ligne de rapprochement : ALPHA et BRAVO ont deux lignes de rapprochement)."""
    points = _par_libelle(await _ok(client_carte, _nationale()))
    assert points["ALPHA"]["nombre"] == 3
    assert points["BRAVO"]["nombre"] == 1
    assert points["BRAVO"]["clients"] == 200
    assert points["HOTEL"]["clients"] == 10
    assert sum(p["nombre"] for p in points.values()) == 13


async def test_clients_du_poste_et_pas_de_l_interruption(client_carte: AsyncClient) -> None:
    """Clients = estimés du poste, sinon touchés du poste, sinon 0 ; jamais les 7777 de l'interruption.
    CHARLIE : 602 (estimé NULL, touchés 40) + 610 (30) = 70."""
    points = _par_libelle(await _ok(client_carte, _nationale()))
    assert points["CHARLIE"]["clients"] == 70
    assert points["ALPHA"]["clients"] == 150
    for point in points.values():
        assert point["clients"] < 7777


async def test_nature_dominante_et_egalites(client_carte: AsyncClient) -> None:
    """Égalité → incident, delestage, travaux, autre : FOXTROT (incident = délestage) → incident ;
    ECHO (travaux = autre) → travaux ; HOTEL (incident = travaux, 609 brouillon compté) → incident ;
    CHARLIE (deux délestages) → delestage."""
    points = _par_libelle(await _ok(client_carte, _nationale()))
    assert points["FOXTROT"]["nature_dominante"] == "incident"
    assert points["ECHO"]["nature_dominante"] == "travaux"
    assert points["HOTEL"]["nature_dominante"] == "incident"
    assert points["CHARLIE"]["nature_dominante"] == "delestage"
    assert points["ALPHA"]["nature_dominante"] == "incident"


# --------------------------------------------------------------------------------------------
# Limite de points
# --------------------------------------------------------------------------------------------


async def test_limite_par_defaut_3000() -> None:
    from app.services import suivi_incidents_service

    assert suivi_incidents_service.LIMITE_POINTS_CARTE == 3000


async def test_limite_tronque_les_postes_les_moins_touches(
    client_carte: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limite 3 : ALPHA (3), puis CHARLIE et ECHO (2, ordre du libellé) ; FOXTROT, HOTEL… écartés."""
    from app.services import suivi_incidents_service

    monkeypatch.setattr(suivi_incidents_service, "LIMITE_POINTS_CARTE", 3)
    data = await _ok(client_carte, _nationale())
    assert [p["libelle"] for p in data["points"]] == ["ALPHA", "CHARLIE", "ECHO"]
    assert data["tronque"] is True
    assert data["postes_touches"] == 13
    assert data["postes_localises"] == 7


async def test_limite_egale_au_nombre_de_localises_non_tronque(
    client_carte: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Limite 7 = postes localisés : rien d'écarté (les non localisés ne comptent pas)."""
    from app.services import suivi_incidents_service

    monkeypatch.setattr(suivi_incidents_service, "LIMITE_POINTS_CARTE", 7)
    data = await _ok(client_carte, _nationale())
    assert data["tronque"] is False
    assert [p["libelle"] for p in data["points"]] == ORDRE_NATIONAL


# --------------------------------------------------------------------------------------------
# Filtres
# --------------------------------------------------------------------------------------------


async def test_periode_vide(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), PERIODE_VIDE)
    assert data == {"postes_touches": 0, "postes_localises": 0, "tronque": False, "points": []}


async def test_filtre_nature(client_carte: AsyncClient) -> None:
    """DELESTAGE (602, 607, 610) : ALPHA 1 (602), CHARLIE 2, FOXTROT 1 (607), JULIET non localisé."""
    data = await _ok(client_carte, _nationale(), {"nature_id": 3})
    assert data["postes_touches"] == 4
    assert data["postes_localises"] == 3
    assert [(p["libelle"], p["nombre"]) for p in data["points"]] == [("CHARLIE", 2), ("ALPHA", 1), ("FOXTROT", 1)]
    alpha = _par_libelle(data)["ALPHA"]
    assert alpha["nature_dominante"] == "delestage"
    assert alpha["clients"] == 50
    assert alpha["duree_heures"] == pytest.approx(0.5, abs=0.01)


async def test_filtre_feeder_de_l_interruption(client_carte: AsyncClient) -> None:
    """feeder_id = 1 filtre les interruptions (601, 602, 603) ; le point garde le feeder du poste
    (CHARLIE : feeder 2)."""
    data = await _ok(client_carte, _nationale(), {"feeder_id": 1})
    assert data["postes_touches"] == 3
    assert [(p["libelle"], p["nombre"]) for p in data["points"]] == [("ALPHA", 3), ("BRAVO", 1), ("CHARLIE", 1)]
    charlie = _par_libelle(data)["CHARLIE"]
    assert (charlie["feeder_id"], charlie["feeder"]) == (2, "HANN DEPART 2")
    assert charlie["clients"] == 40


async def test_filtre_region_par_un_national(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _nationale(), {"region_id": 2})
    assert data["postes_touches"] == 3
    assert [(p["libelle"], p["nombre"]) for p in data["points"]] == [("FOXTROT", 2)]


@pytest.mark.parametrize(
    "params",
    [
        {"debut": "2026-11-20", "fin": "2026-11-14"},
        {"reseau": "bt"},
        {"debut": "2020-01-01", "fin": "2026-11-20"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_carte: AsyncClient, params: dict[str, Any]) -> None:
    response = await appeler(client_carte, URL, _nationale(), {**SEMAINE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


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
    assert data["postes_localises"] == 7


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_carte: AsyncClient, role: str) -> None:
    """Région 2 (606, 607) : FOXTROT, KILO, MIKE touchés ; FOXTROT seul localisé."""
    data = await _ok(client_carte, _make_user(role, scope_service_id=2))
    assert data["postes_touches"] == 3
    assert data["postes_localises"] == 1
    assert [(p["libelle"], p["nombre"], p["clients"]) for p in data["points"]] == [("FOXTROT", 2, 600)]


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_dakar(client_carte: AsyncClient, role: str) -> None:
    """Région 1 : tout sauf 606, 607 → 10 postes touchés, 6 localisés (FOXTROT absent)."""
    data = await _ok(client_carte, _make_user(role, scope_service_id=1))
    assert data["postes_touches"] == 10
    assert data["postes_localises"] == 6
    assert "FOXTROT" not in _par_libelle(data)


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_carte: AsyncClient, role: str) -> None:
    response = await appeler(client_carte, URL, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 1})
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_carte: AsyncClient) -> None:
    data = await _ok(client_carte, _make_user("BCC", scope_service_id=2), {"service_id": 1})
    assert data == {"postes_touches": 0, "postes_localises": 0, "tronque": False, "points": []}


async def test_superviseur_limite_a_son_service(client_carte: AsyncClient) -> None:
    """SDPG (604, 605) : DELTA et ECHO touchés, ECHO localisé."""
    data = await _ok(client_carte, _make_user("SUPERVISEUR", scope_service_id=2))
    assert data["postes_touches"] == 2
    assert [(p["libelle"], p["nombre"]) for p in data["points"]] == [("ECHO", 2)]


async def test_superviseur_autre_service_403(client_carte: AsyncClient) -> None:
    response = await appeler(
        client_carte, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**SEMAINE, "service_id": 2}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_cle_suivi_carte_ttl_une_heure(client_carte: AsyncClient, fake_redis: Any) -> None:
    await _ok(client_carte, _nationale())
    cles = [c async for c in fake_redis.scan_iter("suivi:carte:*")]
    assert cles, "aucune clé suivi:carte:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_deuxieme_appel_servi_par_le_cache(client_carte: AsyncClient, session_carte: AsyncSession) -> None:
    premier = await _ok(client_carte, _nationale())
    await session_carte.execute(text("DELETE FROM poste_interruptions"))
    await session_carte.commit()
    second = await _ok(client_carte, _nationale())
    assert second == premier


async def test_cache_distinct_par_perimetre(client_carte: AsyncClient) -> None:
    national = await _ok(client_carte, _nationale())
    regional = await _ok(client_carte, _make_user("BCC", scope_service_id=2))
    assert national["postes_touches"] == 13
    assert regional["postes_touches"] == 3
