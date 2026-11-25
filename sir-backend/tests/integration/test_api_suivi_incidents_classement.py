"""GET /api/v1/suivi-incidents/classement — classement par service, poste source ou feeder (§8).

Paramètres : filtres communs + ``niveau`` (service | poste_source | feeder, obligatoire) et
``limite`` (1 à 50, défaut 10). Réponse ``ApiResponse[ClassementSuivi]`` : niveau,
total_interruptions, lignes ({id, code, libelle, nombre, duree_heures, end_mwh, part}), autres.
Tri : nombre décroissant puis libellé ; « Non renseigné » (id null) toujours dernière, hors limite ;
``autres`` = somme des lignes au-delà de la limite, null s'il n'y en a pas.

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

URL = "/api/v1/suivi-incidents/classement"
APPROX = {"abs": 0.01}
CHAMPS_LIGNE = {"id", "code", "libelle", "nombre", "duree_heures", "end_mwh", "part"}


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any]) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **params})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    return corps["data"]


def _resume(data: dict[str, Any]) -> list[tuple[Any, int]]:
    return [(ligne["id"], ligne["nombre"]) for ligne in data["lignes"]]


def _verifier_ligne(ligne: dict[str, Any], nombre: int, duree_h: float, end: float, total: int) -> None:
    assert ligne["nombre"] == nombre, ligne
    assert ligne["duree_heures"] == pytest.approx(duree_h, **APPROX), ligne
    assert ligne["end_mwh"] == pytest.approx(end, **APPROX), ligne
    assert ligne["part"] == pytest.approx(nombre / total, abs=1e-3), ligne


# --------------------------------------------------------------------------------------------
# Niveaux, tri, « Non renseigné »
# --------------------------------------------------------------------------------------------


async def test_classement_par_service(client_suivi: AsyncClient) -> None:
    """DRS (3) et SDDV (3) départagés par le libellé (« Direction… » avant « Service… »), puis
    SDPG (2), puis « Non renseigné » (108)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service"})
    assert data["niveau"] == "service"
    assert data["total_interruptions"] == 9
    assert data["autres"] is None
    lignes = data["lignes"]
    assert _resume(data) == [(3, 3), (1, 3), (2, 2), (None, 1)]
    for ligne in lignes:
        assert set(ligne) == CHAMPS_LIGNE
    drs, sddv, sdpg, sans = lignes
    assert (drs["code"], drs["libelle"]) == ("DRS", "Direction Regionale Sud")
    assert (sddv["code"], sddv["libelle"]) == ("SDDV", "Service Dakar Ville")
    assert (sdpg["code"], sdpg["libelle"]) == ("SDPG", "Service Pikine Guediawaye")
    assert sans["libelle"] == "Non renseigné"
    _verifier_ligne(drs, 3, 255 / 60, 1.05, 9)
    _verifier_ligne(sddv, 3, 195 / 60, 3.2, 9)
    _verifier_ligne(sdpg, 2, 2.5, 5.5, 9)
    _verifier_ligne(sans, 1, 10 / 60, 0.1, 9)
    assert sum(ligne["part"] for ligne in lignes) == pytest.approx(1.0, abs=1e-3)


async def test_classement_par_poste_source_non_renseigne_dernier(client_suivi: AsyncClient) -> None:
    """« Non renseigné » (105, 108, 109 : 3) reste dernier même plus grand que SOCOCIM et KAOLACK."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "poste_source"})
    assert data["niveau"] == "poste_source"
    assert data["total_interruptions"] == 9
    assert _resume(data) == [(1, 3), (2, 2), (3, 1), (None, 3)]
    hann, sococim, kaolack, sans = data["lignes"]
    assert (hann["code"], hann["libelle"]) == ("PS-HANN", "HANN")
    assert sococim["libelle"] == "SOCOCIM" and kaolack["libelle"] == "KAOLACK"
    assert sans["libelle"] == "Non renseigné"
    _verifier_ligne(hann, 3, 195 / 60, 3.2, 9)
    _verifier_ligne(sococim, 2, 2.5, 5.5, 9)
    _verifier_ligne(kaolack, 1, 4.0, 1.0, 9)
    _verifier_ligne(sans, 3, 25 / 60, 0.15, 9)
    assert data["autres"] is None


async def test_classement_par_feeder_egalites_par_libelle(client_suivi: AsyncClient) -> None:
    """2 : BEL AIR 2 puis HANN DEPART 1 ; 1 : HANN DEPART 2 puis KAOLACK VILLE ; puis Non renseigné."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    assert data["niveau"] == "feeder"
    assert _resume(data) == [(3, 2), (1, 2), (2, 1), (4, 1), (None, 3)]
    assert [ligne["libelle"] for ligne in data["lignes"]] == [
        "BEL AIR 2", "HANN DEPART 1", "HANN DEPART 2", "KAOLACK VILLE", "Non renseigné",
    ]
    assert [ligne["code"] for ligne in data["lignes"][:4]] == ["F-BELAIR-2", "F-HANN-1", "F-HANN-2", "F-KAO-V"]
    _verifier_ligne(data["lignes"][0], 2, 2.5, 5.5, 9)
    _verifier_ligne(data["lignes"][1], 2, 165 / 60, 2.7, 9)
    assert data["total_interruptions"] == 9


# --------------------------------------------------------------------------------------------
# Limite et « autres »
# --------------------------------------------------------------------------------------------


async def test_limite_1_autres_somme_au_dela(client_suivi: AsyncClient) -> None:
    """limite=1 : DRS, puis « Non renseigné » (hors limite) ; autres = SDDV + SDPG."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service", "limite": 1})
    assert _resume(data) == [(3, 3), (None, 1)]
    assert data["total_interruptions"] == 9
    autres = data["autres"]
    assert autres is not None
    assert autres["nombre"] == 5
    assert autres["duree_heures"] == pytest.approx(345 / 60, **APPROX)
    assert autres["end_mwh"] == pytest.approx(8.7, **APPROX)
    assert autres["part"] == pytest.approx(5 / 9, abs=1e-3)
    total_parts = sum(ligne["part"] for ligne in data["lignes"]) + autres["part"]
    assert total_parts == pytest.approx(1.0, abs=1e-3)


async def test_limite_2_autres_une_ligne(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service", "limite": 2})
    assert _resume(data) == [(3, 3), (1, 3), (None, 1)]
    assert data["autres"]["nombre"] == 2
    assert data["autres"]["end_mwh"] == pytest.approx(5.5, **APPROX)


@pytest.mark.parametrize("limite", [3, 50])
async def test_limite_suffisante_autres_null(client_suivi: AsyncClient, limite: int) -> None:
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service", "limite": limite})
    assert len(data["lignes"]) == 4
    assert data["autres"] is None


async def test_limite_par_defaut_10(client_suivi: AsyncClient) -> None:
    """Sans limite : 10 lignes rattachées au plus (ici 4 feeders + Non renseigné), autres null."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    assert len(data["lignes"]) == 5
    assert data["autres"] is None


async def test_periode_vide(client_suivi: AsyncClient) -> None:
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"),
        {"niveau": "service", "debut": "2026-12-05", "fin": "2026-12-11"},
    )
    assert data["total_interruptions"] == 0
    assert data["lignes"] == []
    assert data["autres"] is None


# --------------------------------------------------------------------------------------------
# Filtres
# --------------------------------------------------------------------------------------------


async def test_filtre_reseau_htb(client_suivi: AsyncClient) -> None:
    """reseau=htb : 103 et 106, toutes deux SDPG."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service", "reseau": "htb"})
    assert data["total_interruptions"] == 2
    assert _resume(data) == [(2, 2)]
    assert data["lignes"][0]["part"] == pytest.approx(1.0)


async def test_filtre_poste_source(client_suivi: AsyncClient) -> None:
    """poste_source_id=1, niveau feeder : HANN DEPART 1 (101, 107) puis HANN DEPART 2 (102)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "poste_source_id": 1})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(1, 2), (2, 1)]


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"niveau": "service", "limite": 0},
        {"niveau": "service", "limite": 51},
        {"niveau": "service", "limite": -1},
        {"niveau": "region"},
        {"niveau": "commune"},
        {"niveau": ""},
        {"niveau": "service", "debut": "2026-11-20", "fin": "2026-11-14"},
    ],
)
async def test_parametres_invalides_422_enveloppe(client_suivi: AsyncClient, params: dict[str, Any]) -> None:
    """limite hors 1..50, niveau inconnu, période invalide → 422 enveloppé."""
    response = await appeler(client_suivi, URL, _make_user("ADMIN_SAQS"), {**SEMAINE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


async def test_niveau_obligatoire_422(client_suivi: AsyncClient) -> None:
    response = await appeler(client_suivi, URL, _make_user("ADMIN_SAQS"), SEMAINE)
    assert response.status_code == 422


# --------------------------------------------------------------------------------------------
# Authentification et périmètre
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client_suivi: AsyncClient) -> None:
    response = await client_suivi.get(URL, params={**SEMAINE, "niveau": "service"})
    assert response.status_code in (401, 403)


async def test_sans_permission_indicateurs_read_403(client_suivi: AsyncClient) -> None:
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await appeler(client_suivi, URL, user, {**SEMAINE, "niveau": "service"})
    assert response.status_code == 403


async def test_role_hors_regle_des_indicateurs_403(client_suivi: AsyncClient) -> None:
    response = await appeler(client_suivi, URL, _make_user("DISPATCHER"), {**SEMAINE, "niveau": "service"})
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national(client_suivi: AsyncClient, role: str) -> None:
    data = await _ok(client_suivi, _make_user(role), {"niveau": "service"})
    assert data["total_interruptions"] == 9


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_suivi: AsyncClient, role: str) -> None:
    """BCC / BRC région 2 : 104, 105, 109 ; poste source KAOLACK (1) puis Non renseigné (2)."""
    data = await _ok(client_suivi, _make_user(role, scope_service_id=2), {"niveau": "poste_source"})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(3, 1), (None, 2)]
    services = await _ok(client_suivi, _make_user(role, scope_service_id=2), {"niveau": "service"})
    assert _resume(services) == [(3, 3)]


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_suivi: AsyncClient, role: str) -> None:
    response = await appeler(
        client_suivi, URL, _make_user(role, scope_service_id=2),
        {**SEMAINE, "niveau": "service", "region_id": 1},
    )
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_suivi: AsyncClient) -> None:
    data = await _ok(
        client_suivi, _make_user("BCC", scope_service_id=2), {"niveau": "service", "service_id": 1}
    )
    assert data["total_interruptions"] == 0
    assert data["lignes"] == []


async def test_superviseur_limite_a_son_service(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("SUPERVISEUR", scope_service_id=1), {"niveau": "feeder"})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(1, 2), (2, 1)]


async def test_superviseur_autre_service_403(client_suivi: AsyncClient) -> None:
    response = await appeler(
        client_suivi, URL, _make_user("SUPERVISEUR", scope_service_id=1),
        {**SEMAINE, "niveau": "service", "service_id": 2},
    )
    assert response.status_code == 403


async def test_cache_par_niveau(client_suivi: AsyncClient) -> None:
    """Le niveau et la limite font partie de la clé : pas de réponse d'un autre niveau en cache."""
    services = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "service"})
    feeders = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    limite = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "limite": 1})
    assert services["niveau"] == "service" and feeders["niveau"] == "feeder"
    assert len(feeders["lignes"]) == 5
    assert len(limite["lignes"]) == 2
