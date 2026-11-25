"""GET /api/v1/suivi-incidents/saifi-saidi — onglet SAIFI / SAIDI (spécification étape 5, §10).

Formule SENELEC existante (``saifi_saidi_service.calculer_perimetre``), sans nouvelle règle :
interruptions distribution clôturées (statut clôturé ET date_remise renseignée) de plus de 5 min ;
NombreClient = Σ clients estimés des postes ; SAIDI en heures ; base clients du mois de la
dernière apparition (clôturées, brèves comprises) sur tout le périmètre, dernier mois connu à défaut.

Données : ``tests/integration/_donnees_saifi_suivi.py`` (tableaux des interruptions et de la base).

Calculs à la main, période P (15/09 → 20/10/2026), national (services 1 à 4) :
- comptées : 501 (1000 clients, 2 h), 502 (2000, 1 h), 503 (300, 4 h), 504 (100, 0,5 h),
  505 (800, 1,5 h), 506 (200, 0,25 h) ; exclues : 507 en cours, 508 de 5 min, 509 brouillon,
  510 sans remise, 511 sans service (hors ``interruptions_du_perimetre``), 512 transport,
  520 / 521 hors période ;
- clients_coupes = 4 400 ; client_heures = 2000 + 2000 + 1200 + 50 + 1200 + 50 = 6 500 ;
- dernière apparition (clôturées, brèves comprises) : 508 le 20/10 → base d'octobre = 20 000 ;
- SAIFI = 4 400 / 20 000 = 0,22 ; SAIDI = 6 500 / 20 000 = 0,325.
Réseaux : HTB = 502 + 505 (2 800 ; 3 200) → 0,14 / 0,16 ; HTA = 501, 503, 504, 506
(1 600 ; 3 300) → 0,08 / 0,165.
Natures : incident 501, 504, 506 (1 300 ; 2 100) ; délestage 502 (2 000 ; 2 000) ;
travaux 503 (300 ; 1 200) ; autre 505 (800 ; 1 200).
Mensuel : septembre (15 → 30) 501, 502, 503 (3 300 ; 5 200) ÷ 17 000 ; octobre (1 → 20)
504, 505, 506 (1 100 ; 1 300) ÷ 20 000 ; cumul d'octobre 4 400 / 20 000 = synthèse.
Services : SDPG 2 800 / 20 000 = 0,14 ; SDDV 1 100 → 0,055 ; DRS 500 → 0,025.
Dakar (région 1) : 501, 502, 504, 505 (3 900 ; 5 250) ÷ 16 000 ; Régions : 503, 506 (500 ; 1 250)
÷ 4 000. SUPERVISEUR SDDV : 501, 504 (1 100 ; 2 050) ÷ 10 000.

Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration._donnees_saifi_suivi import (  # noqa: F401 (fixtures)
    PERIODE,
    PERIODE_B,
    PERIODE_C,
    PERIODE_J,
    _make_user,
    appeler,
    client_saifi,
    erreur_enveloppee,
    session_saifi,
)

pytestmark = pytest.mark.asyncio

URL = "/api/v1/suivi-incidents/saifi-saidi"
CHAMPS_INDICATEUR = {"saifi", "saidi", "interruptions", "clients_coupes", "client_heures", "clients_reference"}
CHAMPS_MENSUEL = {"annee", "mois", "libelle", "saifi", "saidi", "saifi_cumule", "saidi_cumule", "interruptions"}


def _approx(valeur: float) -> Any:
    return pytest.approx(valeur, abs=1e-4)


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any] | None = None, periode: dict[str, str] = PERIODE) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**periode, **(params or {})})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    return corps["data"]


def _indicateur(
    ligne: dict[str, Any],
    clients: int,
    client_heures: float,
    interruptions: int,
    reference: int,
) -> None:
    assert CHAMPS_INDICATEUR <= set(ligne), ligne
    assert ligne["interruptions"] == interruptions, ligne
    assert ligne["clients_coupes"] == clients, ligne
    assert ligne["client_heures"] == _approx(client_heures), ligne
    assert ligne["clients_reference"] == reference, ligne
    attendu_saifi = clients / reference if reference else 0.0
    attendu_saidi = client_heures / reference if reference else 0.0
    assert ligne["saifi"] == _approx(attendu_saifi), ligne
    assert ligne["saidi"] == _approx(attendu_saidi), ligne


def _par_cle(lignes: list[dict[str, Any]], cle: str) -> dict[Any, dict[str, Any]]:
    return {ligne[cle]: ligne for ligne in lignes}


ADMIN = _make_user("ADMIN_SAQS")


# --------------------------------------------------------------------------------------------
# Authentification, droits, validation
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client_saifi: AsyncClient) -> None:
    response = await client_saifi.get(URL, params=PERIODE)
    assert response.status_code in (401, 403)


async def test_jeton_invalide_401(client_saifi: AsyncClient) -> None:
    response = await client_saifi.get(URL, params=PERIODE, headers={"Authorization": "Bearer pas-un-jwt"})
    assert response.status_code == 401


async def test_sans_permission_indicateurs_read_403(client_saifi: AsyncClient) -> None:
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await appeler(client_saifi, URL, user, PERIODE)
    assert response.status_code == 403


async def test_role_hors_regle_des_indicateurs_403(client_saifi: AsyncClient) -> None:
    """DISPATCHER (transport) avec indicateurs:read : hors règle des indicateurs distribution."""
    response = await appeler(client_saifi, URL, _make_user("DISPATCHER"), PERIODE)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "params",
    [
        {"debut": "2026-10-20", "fin": "2026-09-15"},
        {"debut": "2020-01-01", "fin": "2026-10-20"},
        {"reseau": "bt"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_saifi: AsyncClient, params: dict[str, Any]) -> None:
    response = await appeler(client_saifi, URL, ADMIN, {**PERIODE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


# --------------------------------------------------------------------------------------------
# Synthèse et règles de la formule
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_synthese_nationale(client_saifi: AsyncClient, role: str) -> None:
    """4 400 clients, 6 500 clients × h, 6 interruptions, base d'octobre 20 000."""
    data = await _ok(client_saifi, _make_user(role))
    _indicateur(data["synthese"], 4400, 6500.0, 6, 20000)
    assert data["synthese"]["saifi"] == _approx(0.22)
    assert data["synthese"]["saidi"] == _approx(0.325)
    assert data["mois_reference"] == {"annee": 2026, "mois": 10}
    assert data["contribution"] is False


async def test_exclusions_en_cours_breves_brouillon_sans_remise_transport(client_saifi: AsyncClient) -> None:
    """507 (en cours), 508 (5 min), 509 (brouillon), 510 (sans remise), 511 (sans service),
    512 (transport) ne comptent pas : 6 interruptions seulement, aucune ligne « Non renseigné »."""
    data = await _ok(client_saifi, ADMIN)
    assert data["synthese"]["interruptions"] == 6
    assert data["synthese"]["clients_coupes"] == 4400
    assert all(ligne["id"] is not None for ligne in data["services"])
    # SDRBD n'a qu'une interruption de 5 minutes : absent des contributions
    assert 4 not in {ligne["id"] for ligne in data["services"]}


async def test_nombre_client_vient_des_postes_et_pas_de_l_interruption(client_saifi: AsyncClient) -> None:
    """interruptions.nombre_clients_touches vaut 7 partout : il n'est pas lu (estimé des postes,
    repli sur les touchés du poste pour 506)."""
    data = await _ok(client_saifi, ADMIN)
    assert data["synthese"]["clients_coupes"] != 6 * 7
    services = _par_cle(data["services"], "id")
    assert services[3]["clients_coupes"] == 500  # 503 (300) + 506 (200, repli touchés du poste)


async def test_mois_reference_derniere_apparition_breve_comprise(client_saifi: AsyncClient) -> None:
    """Période C : 540 (10/08, 600 clients, 1 h) comptée ; 541 (05/09, 5 min) non comptée mais
    dernière apparition clôturée → base de septembre 17 000 (pas août 16 000)."""
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_C)
    _indicateur(data["synthese"], 600, 600.0, 1, 17000)
    assert data["mois_reference"] == {"annee": 2026, "mois": 9}


async def test_dernier_mois_connu_a_defaut_de_base(client_saifi: AsyncClient) -> None:
    """Période B : 530 en novembre, pas de photo de novembre → base d'octobre (20 000)."""
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_B)
    _indicateur(data["synthese"], 600, 600.0, 1, 20000)
    assert data["synthese"]["saifi"] == _approx(0.03)
    assert data["mois_reference"] == {"annee": 2026, "mois": 10}


async def test_sans_base_clients(client_saifi: AsyncClient) -> None:
    """Période J (janvier 2026) : aucune photo antérieure → SAIFI / SAIDI à 0, mois_reference null."""
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_J)
    _indicateur(data["synthese"], 600, 600.0, 1, 0)
    assert data["synthese"]["saifi"] == 0
    assert data["mois_reference"] is None


@pytest.mark.parametrize("periode", [PERIODE, PERIODE_B, PERIODE_C], ids=["P", "B", "C"])
async def test_egal_a_calculer_perimetre_national(
    client_saifi: AsyncClient, session_saifi: AsyncSession, periode: dict[str, str]
) -> None:
    """Sans filtre : synthèse = calculer_perimetre(service_ids, debut, fin + 1 jour)."""
    from app.repositories.perimetre import perimetre_region
    from app.services import saifi_saidi_service

    data = await _ok(client_saifi, ADMIN, periode=periode)
    debut = datetime.fromisoformat(periode["debut"])
    fin = datetime.fromisoformat(periode["fin"]) + timedelta(days=1)
    with perimetre_region(None):
        attendu = await saifi_saidi_service.calculer_perimetre(
            session_saifi, [1, 2, 3, 4], debut, fin, today=date(2026, 11, 25)
        )
    assert data["synthese"]["saifi"] == _approx(attendu.saifi)
    assert data["synthese"]["saidi"] == _approx(attendu.saidi)
    assert data["synthese"]["interruptions"] == attendu.nombre_interruptions
    assert data["synthese"]["clients_reference"] == attendu.total_clients_reference


async def test_egal_a_calculer_perimetre_region_et_service(
    client_saifi: AsyncClient, session_saifi: AsyncSession
) -> None:
    from app.repositories.perimetre import perimetre_region
    from app.services import saifi_saidi_service

    debut = datetime(2026, 9, 15)
    fin = datetime(2026, 10, 21)
    dakar = await _ok(client_saifi, _make_user("BCC", scope_service_id=1))
    with perimetre_region(1):
        attendu = await saifi_saidi_service.calculer_perimetre(session_saifi, [1, 2, 3, 4], debut, fin)
    assert dakar["synthese"]["saifi"] == _approx(attendu.saifi)
    assert dakar["synthese"]["saidi"] == _approx(attendu.saidi)
    assert dakar["synthese"]["clients_reference"] == attendu.total_clients_reference

    service = await _ok(client_saifi, _make_user("SUPERVISEUR", scope_service_id=1))
    with perimetre_region(None):
        attendu = await saifi_saidi_service.calculer_perimetre(session_saifi, [1], debut, fin)
    assert service["synthese"]["saifi"] == _approx(attendu.saifi)
    assert service["synthese"]["saidi"] == _approx(attendu.saidi)
    assert service["synthese"]["clients_reference"] == attendu.total_clients_reference


# --------------------------------------------------------------------------------------------
# Réseaux et natures
# --------------------------------------------------------------------------------------------


async def test_reseaux_hta_htb_total(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN)
    assert [ligne["reseau"] for ligne in data["reseaux"]] == ["hta", "htb", "total"]
    reseaux = _par_cle(data["reseaux"], "reseau")
    _indicateur(reseaux["hta"], 1600, 3300.0, 4, 20000)
    _indicateur(reseaux["htb"], 2800, 3200.0, 2, 20000)
    _indicateur(reseaux["total"], 4400, 6500.0, 6, 20000)
    for cle in ("saifi", "saidi", "clients_coupes", "interruptions"):
        assert reseaux["hta"][cle] + reseaux["htb"][cle] == _approx(reseaux["total"][cle])


async def test_natures_somme_egale_synthese_et_parts(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN)
    assert [n["categorie"] for n in data["natures"]] == ["incident", "delestage", "travaux", "autre"]
    assert [n["libelle"] for n in data["natures"]] == ["Incidents", "Délestages", "Travaux", "Autres coupures"]
    natures = _par_cle(data["natures"], "categorie")
    _indicateur(natures["incident"], 1300, 2100.0, 3, 20000)
    _indicateur(natures["delestage"], 2000, 2000.0, 1, 20000)
    _indicateur(natures["travaux"], 300, 1200.0, 1, 20000)
    _indicateur(natures["autre"], 800, 1200.0, 1, 20000)
    assert sum(n["saifi"] for n in data["natures"]) == _approx(data["synthese"]["saifi"])
    assert sum(n["saidi"] for n in data["natures"]) == _approx(data["synthese"]["saidi"])
    assert natures["incident"]["part_saifi"] == _approx(1300 / 4400)
    assert natures["delestage"]["part_saifi"] == _approx(2000 / 4400)
    assert sum(n["part_saifi"] for n in data["natures"]) == _approx(1.0)


async def test_parts_nulles_sans_base(client_saifi: AsyncClient) -> None:
    """Synthèse nulle (aucune base) : part_saifi = 0, pas de division par zéro."""
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_J)
    assert all(n["part_saifi"] == 0 for n in data["natures"])
    assert all(s["part_saifi"] == 0 for s in data["services"])


# --------------------------------------------------------------------------------------------
# Mensuel
# --------------------------------------------------------------------------------------------


async def test_mensuel_rogne_base_du_mois_et_cumul(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN)
    mensuel = data["mensuel"]
    assert [(p["annee"], p["mois"], p["libelle"]) for p in mensuel] == [
        (2026, 9, "sept. 2026"),
        (2026, 10, "oct. 2026"),
    ]
    for point in mensuel:
        assert CHAMPS_MENSUEL <= set(point), point
    septembre, octobre = mensuel
    # 520 (14/09) hors période : septembre = 501, 502, 503
    assert septembre["interruptions"] == 3
    assert septembre["saifi"] == _approx(3300 / 17000)
    assert septembre["saidi"] == _approx(5200 / 17000)
    assert septembre["saifi_cumule"] == _approx(3300 / 17000)
    assert octobre["interruptions"] == 3
    assert octobre["saifi"] == _approx(1100 / 20000)
    assert octobre["saidi"] == _approx(1300 / 20000)
    assert octobre["saifi_cumule"] == _approx(4400 / 20000)
    assert octobre["saidi_cumule"] == _approx(6500 / 20000)
    # dernier mois = mois de la dernière apparition : cumul = synthèse
    assert octobre["saifi_cumule"] == _approx(data["synthese"]["saifi"])
    assert octobre["saidi_cumule"] == _approx(data["synthese"]["saidi"])


async def test_mensuel_mois_vide_et_cumul_sur_base_du_mois(client_saifi: AsyncClient) -> None:
    """Période C : août 540 ÷ 16 000 ; septembre (1 → 10) sans interruption comptée, présent,
    cumul 600 ÷ 17 000 = synthèse."""
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_C)
    aout, septembre = data["mensuel"]
    assert (aout["mois"], septembre["mois"]) == (8, 9)
    assert aout["saifi"] == _approx(600 / 16000)
    assert aout["saifi_cumule"] == _approx(600 / 16000)
    assert septembre["interruptions"] == 0
    assert septembre["saifi"] == 0 and septembre["saidi"] == 0
    assert septembre["saifi_cumule"] == _approx(600 / 17000)
    assert septembre["saifi_cumule"] == _approx(data["synthese"]["saifi"])


async def test_mensuel_mois_sans_photo_prend_le_dernier_connu(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN, periode=PERIODE_B)
    assert [(p["annee"], p["mois"], p["libelle"]) for p in data["mensuel"]] == [(2026, 11, "nov. 2026")]
    assert data["mensuel"][0]["saifi"] == _approx(600 / 20000)


async def test_mensuel_somme_des_interruptions(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN)
    assert sum(p["interruptions"] for p in data["mensuel"]) == data["synthese"]["interruptions"]


# --------------------------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------------------------


async def test_services_tri_et_parts(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN)
    services = data["services"]
    assert [(s["id"], s["code"], s["libelle"]) for s in services] == [
        (2, "SDPG", "Service Pikine Guediawaye"),
        (1, "SDDV", "Service Dakar Ville"),
        (3, "DRS", "Direction Regionale Sud"),
    ]
    _indicateur(services[0], 2800, 3200.0, 2, 20000)
    _indicateur(services[1], 1100, 2050.0, 2, 20000)
    _indicateur(services[2], 500, 1250.0, 2, 20000)
    assert services[0]["part_saifi"] == _approx(0.14 / 0.22)
    assert sum(s["part_saifi"] for s in services) == _approx(1.0)


# --------------------------------------------------------------------------------------------
# Contribution (filtres du numérateur)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("params", "clients", "client_heures", "interruptions"),
    [
        ({"poste_source_id": 1}, 1100, 2050.0, 2),  # 501, 504 (508 : 5 min)
        ({"nature_id": 3}, 2000, 2000.0, 1),  # 502
        ({"reseau": "htb"}, 2800, 3200.0, 2),  # 502, 505
        ({"exogene": "true"}, 100, 50.0, 1),  # 504
        ({"service_id": 1}, 1100, 2050.0, 2),  # service choisi par un national
    ],
    ids=["poste_source", "nature", "reseau", "exogene", "service_national"],
)
async def test_contribution_avec_filtre(
    client_saifi: AsyncClient, params: dict[str, Any], clients: int, client_heures: float, interruptions: int
) -> None:
    """Le filtre ne touche que le numérateur : base nationale d'octobre (20 000) inchangée."""
    data = await _ok(client_saifi, ADMIN, params)
    assert data["contribution"] is True
    _indicateur(data["synthese"], clients, client_heures, interruptions, 20000)
    assert data["mois_reference"] == {"annee": 2026, "mois": 10}


async def test_mois_reference_calcule_sans_les_autres_filtres(client_saifi: AsyncClient) -> None:
    """nature_id=3 : seule 502 (septembre) est retenue, mais la base reste celle d'octobre (mois de
    la dernière apparition du périmètre) : 2 000 / 20 000 = 0,1 (et non 2 000 / 17 000)."""
    data = await _ok(client_saifi, ADMIN, {"nature_id": 3})
    assert data["synthese"]["saifi"] == _approx(0.1)
    assert data["synthese"]["clients_reference"] == 20000
    # mensuel : septembre ÷ 17 000, octobre vide, cumul d'octobre = synthèse
    septembre, octobre = data["mensuel"]
    assert septembre["saifi"] == _approx(2000 / 17000)
    assert octobre["interruptions"] == 0
    assert octobre["saifi_cumule"] == _approx(0.1)


async def test_contribution_htb_egale_ligne_htb_sans_filtre(client_saifi: AsyncClient) -> None:
    sans_filtre = await _ok(client_saifi, ADMIN)
    htb = await _ok(client_saifi, ADMIN, {"reseau": "htb"})
    ligne_htb = _par_cle(sans_filtre["reseaux"], "reseau")["htb"]
    assert htb["synthese"]["saifi"] == _approx(ligne_htb["saifi"])
    assert htb["synthese"]["saidi"] == _approx(ligne_htb["saidi"])


async def test_pas_de_contribution_pour_la_region_choisie_par_un_national(client_saifi: AsyncClient) -> None:
    data = await _ok(client_saifi, ADMIN, {"region_id": 1})
    assert data["contribution"] is False
    _indicateur(data["synthese"], 3900, 5250.0, 4, 16000)


# --------------------------------------------------------------------------------------------
# Périmètre (dénominateur)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_region_dakar_base_de_la_region_seulement(client_saifi: AsyncClient, role: str) -> None:
    """Région 1 imposée : 501, 502, 504, 505 ÷ base Dakar d'octobre (SDDV + SDPG = 16 000)."""
    data = await _ok(client_saifi, _make_user(role, scope_service_id=1))
    assert data["contribution"] is False
    _indicateur(data["synthese"], 3900, 5250.0, 4, 16000)
    assert data["mois_reference"] == {"annee": 2026, "mois": 10}
    assert {s["id"] for s in data["services"]} == {1, 2}


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_region_regions_base_de_la_region_seulement(client_saifi: AsyncClient, role: str) -> None:
    """Région 2 : 503, 506 ÷ base DRS d'octobre 4 000 → 0,125 / 0,3125."""
    data = await _ok(client_saifi, _make_user(role, scope_service_id=2))
    _indicateur(data["synthese"], 500, 1250.0, 2, 4000)
    assert data["synthese"]["saifi"] == _approx(0.125)
    assert data["synthese"]["saidi"] == _approx(0.3125)
    assert [s["id"] for s in data["services"]] == [3]


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_regional_autre_region_403(client_saifi: AsyncClient, role: str) -> None:
    response = await appeler(
        client_saifi, URL, _make_user(role, scope_service_id=2), {**PERIODE, "region_id": 1}
    )
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_saifi: AsyncClient) -> None:
    """BCC Régions qui choisit SDDV (Dakar) : région imposée, aucune interruption, base Régions."""
    data = await _ok(client_saifi, _make_user("BCC", scope_service_id=2), {"service_id": 1})
    assert data["synthese"]["interruptions"] == 0
    assert data["synthese"]["saifi"] == 0
    assert data["synthese"]["clients_reference"] == 4000
    assert data["services"] == []


async def test_superviseur_son_service(client_saifi: AsyncClient) -> None:
    """SUPERVISEUR SDDV : 501, 504 ÷ base SDDV d'octobre 10 000 → 0,11 / 0,205."""
    data = await _ok(client_saifi, _make_user("SUPERVISEUR", scope_service_id=1))
    assert data["contribution"] is False
    _indicateur(data["synthese"], 1100, 2050.0, 2, 10000)
    assert [s["id"] for s in data["services"]] == [1]


async def test_superviseur_autre_service_403(client_saifi: AsyncClient) -> None:
    response = await appeler(
        client_saifi, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**PERIODE, "service_id": 2}
    )
    assert response.status_code == 403


async def test_superviseur_region_403(client_saifi: AsyncClient) -> None:
    response = await appeler(
        client_saifi, URL, _make_user("SUPERVISEUR", scope_service_id=1), {**PERIODE, "region_id": 1}
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_cle_saifi_saidi_ttl_une_heure(client_saifi: AsyncClient, fake_redis: Any) -> None:
    await _ok(client_saifi, ADMIN)
    cles = [c async for c in fake_redis.scan_iter("suivi:saifi-saidi:*")]
    assert cles, "aucune clé suivi:saifi-saidi:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_cache_distinct_par_perimetre(client_saifi: AsyncClient) -> None:
    """Mêmes filtres (service_id=1) mais périmètres différents : national (contribution, base
    20 000) puis SUPERVISEUR SDDV (base 10 000) ; le second ne reçoit pas le premier."""
    national = await _ok(client_saifi, ADMIN, {"service_id": 1})
    superviseur = await _ok(client_saifi, _make_user("SUPERVISEUR", scope_service_id=1))
    assert national["synthese"]["clients_reference"] == 20000
    assert national["contribution"] is True
    assert superviseur["synthese"]["clients_reference"] == 10000
    assert superviseur["contribution"] is False

    bcc = await _ok(client_saifi, _make_user("BCC", scope_service_id=2))
    tout = await _ok(client_saifi, ADMIN)
    bcc_bis = await _ok(client_saifi, _make_user("BCC", scope_service_id=2))
    assert bcc["synthese"]["clients_reference"] == 4000
    assert tout["synthese"]["clients_reference"] == 20000
    assert bcc_bis["synthese"] == bcc["synthese"]
