"""GET /api/v1/suivi-incidents/reseau et /reseau/export — onglet Réseau (spécification étape 4, §9).

Paramètres : filtres communs + ``niveau`` = poste_source | feeder (obligatoire ; absent, « service »
ou inconnu → 422 enveloppé). Réponse ``ApiResponse[ReseauSuivi]`` : niveau, total_interruptions,
lignes — **toutes** (pas de limite), triées par nombre décroissant puis libellé, « Non renseigné »
(id null) en dernier. Ligne :
``{id, code, libelle, poste_source, nombre, duree_heures, end_mwh, coupures_clients, postes_touches, part}``
(``poste_source`` = libellé du poste source **du feeder** au niveau feeder, null au niveau
poste_source ; ``postes_touches`` = postes distincts de poste_interruptions).

Export Excel : mêmes paramètres, droits et périmètre ; fichier
``suivi_{niveau}_{debut}_{fin}.xlsx`` ; une feuille : titre, en-tête, lignes de /reseau dans le même ordre.

Données : ``tests/integration/_donnees_suivi_incidents.py``.
Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

from io import BytesIO
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

URL = "/api/v1/suivi-incidents/reseau"
URL_EXPORT = "/api/v1/suivi-incidents/reseau/export"
APPROX = {"abs": 0.01}
CHAMPS_LIGNE = {
    "id", "code", "libelle", "poste_source", "nombre", "duree_heures", "end_mwh",
    "coupures_clients", "postes_touches", "part",
}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OCTOBRE = {"debut": "2026-10-01", "fin": "2026-10-31"}
MARS = {"debut": "2026-03-01", "fin": "2026-03-31"}


async def _ok(client: AsyncClient, user: Any, params: dict[str, Any]) -> dict[str, Any]:
    response = await appeler(client, URL, user, {**SEMAINE, **params})
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    data = corps["data"]
    for ligne in data["lignes"]:
        assert set(ligne) == CHAMPS_LIGNE, ligne
    return data


def _resume(data: dict[str, Any]) -> list[tuple[Any, int]]:
    return [(ligne["id"], ligne["nombre"]) for ligne in data["lignes"]]


def _ligne(
    ligne: dict[str, Any],
    *,
    nombre: int,
    duree_h: float,
    end: float,
    clients: int,
    postes: int,
    total: int,
) -> None:
    assert ligne["nombre"] == nombre, ligne
    assert ligne["duree_heures"] == pytest.approx(duree_h, **APPROX), ligne
    assert ligne["end_mwh"] == pytest.approx(end, **APPROX), ligne
    assert ligne["coupures_clients"] == clients, ligne
    assert ligne["postes_touches"] == postes, ligne
    assert ligne["part"] == pytest.approx(nombre / total, abs=1e-3), ligne


# --------------------------------------------------------------------------------------------
# Niveau poste source
# --------------------------------------------------------------------------------------------


async def test_niveau_poste_source(client_suivi: AsyncClient) -> None:
    """S47 : HANN (101, 102, 107), SOCOCIM (103, 106), KAOLACK (104), Non renseigné (105, 108, 109).

    Postes distincts : HANN {P1, P2, P3} = 3 (P1 et P2 vus deux fois) ; SOCOCIM {P4} = 1.
    """
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "poste_source"})
    assert data["niveau"] == "poste_source"
    assert data["total_interruptions"] == 9
    assert _resume(data) == [(1, 3), (2, 2), (3, 1), (None, 3)]
    hann, sococim, kaolack, sans = data["lignes"]
    assert (hann["code"], hann["libelle"]) == ("PS-HANN", "HANN")
    assert (sococim["code"], sococim["libelle"]) == ("PS-SOC", "SOCOCIM")
    assert (kaolack["code"], kaolack["libelle"]) == ("PS-KAO", "KAOLACK")
    assert (sans["id"], sans["code"], sans["libelle"]) == (None, None, "Non renseigné")
    for ligne in data["lignes"]:
        assert ligne["poste_source"] is None
    _ligne(hann, nombre=3, duree_h=195 / 60, end=3.2, clients=1600, postes=3, total=9)
    _ligne(sococim, nombre=2, duree_h=2.5, end=5.5, clients=2800, postes=1, total=9)
    _ligne(kaolack, nombre=1, duree_h=4.0, end=1.0, clients=300, postes=1, total=9)
    _ligne(sans, nombre=3, duree_h=25 / 60, end=0.15, clients=70, postes=0, total=9)
    assert sum(ligne["part"] for ligne in data["lignes"]) == pytest.approx(1.0, abs=1e-3)


# --------------------------------------------------------------------------------------------
# Niveau feeder
# --------------------------------------------------------------------------------------------


async def test_niveau_feeder(client_suivi: AsyncClient) -> None:
    """S47 : égalités départagées par le libellé ; poste_source = libellé du poste source du feeder."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    assert data["niveau"] == "feeder"
    assert data["total_interruptions"] == 9
    assert _resume(data) == [(3, 2), (1, 2), (2, 1), (4, 1), (None, 3)]
    assert [(ligne["code"], ligne["libelle"], ligne["poste_source"]) for ligne in data["lignes"]] == [
        ("F-BELAIR-2", "BEL AIR 2", "SOCOCIM"),
        ("F-HANN-1", "HANN DEPART 1", "HANN"),
        ("F-HANN-2", "HANN DEPART 2", "HANN"),
        ("F-KAO-V", "KAOLACK VILLE", "KAOLACK"),
        (None, "Non renseigné", None),
    ]
    bel_air, hann_1, hann_2, kaolack, sans = data["lignes"]
    _ligne(bel_air, nombre=2, duree_h=2.5, end=5.5, clients=2800, postes=1, total=9)
    _ligne(hann_1, nombre=2, duree_h=165 / 60, end=2.7, clients=1100, postes=2, total=9)
    _ligne(hann_2, nombre=1, duree_h=0.5, end=0.5, clients=500, postes=2, total=9)
    _ligne(kaolack, nombre=1, duree_h=4.0, end=1.0, clients=300, postes=1, total=9)
    _ligne(sans, nombre=3, duree_h=25 / 60, end=0.15, clients=70, postes=0, total=9)


async def test_feeder_poste_source_du_feeder(client_suivi: AsyncClient) -> None:
    """Octobre : 304 sur HANN DEPART 1 sans poste source saisi → « HANN » (celui du feeder) ;
    305 et 306 sur DEPART ISOLE (feeder sans poste source) → null ; P6 compté une fois."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {**OCTOBRE, "niveau": "feeder"})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(5, 2), (1, 1)]
    isole, hann_1 = data["lignes"]
    assert (isole["code"], isole["libelle"], isole["poste_source"]) == ("F-ISOLE", "DEPART ISOLE", None)
    assert (hann_1["libelle"], hann_1["poste_source"]) == ("HANN DEPART 1", "HANN")
    _ligne(isole, nombre=2, duree_h=40 / 60, end=0.5, clients=230, postes=1, total=3)
    _ligne(hann_1, nombre=1, duree_h=1.0, end=0.3, clients=100, postes=2, total=3)


async def test_poste_source_de_l_interruption_au_niveau_poste_source(client_suivi: AsyncClient) -> None:
    """Octobre, niveau poste_source : poste source de l'interruption non saisi → Non renseigné."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {**OCTOBRE, "niveau": "poste_source"})
    assert _resume(data) == [(None, 3)]
    _ligne(data["lignes"][0], nombre=3, duree_h=100 / 60, end=0.8, clients=330, postes=3, total=3)


async def test_toutes_les_lignes_sans_limite(client_suivi: AsyncClient) -> None:
    """Mars : 12 feeders d'une interruption chacun (au-delà de la limite 10 du classement)."""
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {**MARS, "niveau": "feeder"})
    assert data["total_interruptions"] == 12
    assert len(data["lignes"]) == 12
    assert [ligne["libelle"] for ligne in data["lignes"]] == [f"MARS DEPART {n}" for n in range(10, 22)]
    for ligne in data["lignes"]:
        assert ligne["poste_source"] == "HANN"
        assert ligne["postes_touches"] == 0
        assert ligne["part"] == pytest.approx(1 / 12, abs=1e-3)
    assert "autres" not in data or data["autres"] is None


async def test_periode_vide(client_suivi: AsyncClient) -> None:
    data = await _ok(
        client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "debut": "2026-12-05", "fin": "2026-12-11"}
    )
    assert data["total_interruptions"] == 0
    assert data["lignes"] == []


# --------------------------------------------------------------------------------------------
# Filtres
# --------------------------------------------------------------------------------------------


async def test_filtre_reseau_htb(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "reseau": "htb"})
    assert data["total_interruptions"] == 2
    assert _resume(data) == [(3, 2)]
    assert data["lignes"][0]["part"] == pytest.approx(1.0)


async def test_filtre_poste_source(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "poste_source_id": 1})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(1, 2), (2, 1)]


# --------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
@pytest.mark.parametrize(
    "params",
    [
        {},  # niveau absent
        {"niveau": ""},
        {"niveau": "service"},
        {"niveau": "region"},
        {"niveau": "commune"},
        {"niveau": "feeder", "debut": "2026-11-20", "fin": "2026-11-14"},
        {"niveau": "feeder", "reseau": "bt"},
    ],
)
async def test_parametres_invalides_422_enveloppe(
    client_suivi: AsyncClient, url: str, params: dict[str, Any]
) -> None:
    response = await appeler(client_suivi, url, _make_user("ADMIN_SAQS"), {**SEMAINE, **params})
    assert response.status_code == 422, response.text
    erreur_enveloppee(response.json())


# --------------------------------------------------------------------------------------------
# Authentification et périmètre (/reseau et /reseau/export)
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
async def test_sans_jeton_refuse(client_suivi: AsyncClient, url: str) -> None:
    response = await client_suivi.get(url, params={**SEMAINE, "niveau": "feeder"})
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
async def test_sans_permission_indicateurs_read_403(client_suivi: AsyncClient, url: str) -> None:
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await appeler(client_suivi, url, user, {**SEMAINE, "niveau": "feeder"})
    assert response.status_code == 403


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
async def test_role_hors_regle_des_indicateurs_403(client_suivi: AsyncClient, url: str) -> None:
    response = await appeler(client_suivi, url, _make_user("DISPATCHER"), {**SEMAINE, "niveau": "feeder"})
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national(client_suivi: AsyncClient, role: str) -> None:
    data = await _ok(client_suivi, _make_user(role), {"niveau": "poste_source"})
    assert data["total_interruptions"] == 9


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_limite_a_sa_region(client_suivi: AsyncClient, role: str) -> None:
    """Région 2 : KAOLACK (104), Non renseigné (105, 109)."""
    data = await _ok(client_suivi, _make_user(role, scope_service_id=2), {"niveau": "poste_source"})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(3, 1), (None, 2)]


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_role_regional_autre_region_403(client_suivi: AsyncClient, url: str, role: str) -> None:
    response = await appeler(
        client_suivi, url, _make_user(role, scope_service_id=2),
        {**SEMAINE, "niveau": "feeder", "region_id": 1},
    )
    assert response.status_code == 403


async def test_bcc_service_d_une_autre_region_ne_fuit_pas(client_suivi: AsyncClient) -> None:
    data = await _ok(
        client_suivi, _make_user("BCC", scope_service_id=2), {"niveau": "feeder", "service_id": 1}
    )
    assert data["total_interruptions"] == 0
    assert data["lignes"] == []


async def test_superviseur_limite_a_son_service(client_suivi: AsyncClient) -> None:
    data = await _ok(client_suivi, _make_user("SUPERVISEUR", scope_service_id=1), {"niveau": "feeder"})
    assert data["total_interruptions"] == 3
    assert _resume(data) == [(1, 2), (2, 1)]


@pytest.mark.parametrize("url", [URL, URL_EXPORT])
async def test_superviseur_autre_service_403(client_suivi: AsyncClient, url: str) -> None:
    response = await appeler(
        client_suivi, url, _make_user("SUPERVISEUR", scope_service_id=1),
        {**SEMAINE, "niveau": "feeder", "service_id": 2},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------------------------
# Cache Redis
# --------------------------------------------------------------------------------------------


async def test_cache_redis_cle_suivi_reseau(client_suivi: AsyncClient, fake_redis: Any) -> None:
    await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    cles = [c async for c in fake_redis.scan_iter("suivi:reseau:*")]
    assert cles, "aucune clé suivi:reseau:* écrite dans Redis"
    for cle in cles:
        assert 0 < await fake_redis.ttl(cle) <= 3600


async def test_cache_par_niveau_et_perimetre(client_suivi: AsyncClient) -> None:
    feeders = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder"})
    postes_sources = await _ok(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "poste_source"})
    bcc = await _ok(client_suivi, _make_user("BCC", scope_service_id=2), {"niveau": "poste_source"})
    assert feeders["niveau"] == "feeder" and len(feeders["lignes"]) == 5
    assert postes_sources["niveau"] == "poste_source" and len(postes_sources["lignes"]) == 4
    assert bcc["total_interruptions"] == 3


# --------------------------------------------------------------------------------------------
# Export Excel
# --------------------------------------------------------------------------------------------


async def _export(client: AsyncClient, user: Any, params: dict[str, Any]):
    response = await appeler(client, URL_EXPORT, user, {**SEMAINE, **params})
    assert response.status_code == 200, response.text[:500]
    assert response.headers["content-type"].startswith(XLSX), response.headers["content-type"]
    return response


def _feuille(contenu: bytes) -> list[tuple[Any, ...]]:
    from openpyxl import load_workbook

    classeur = load_workbook(BytesIO(contenu), read_only=True, data_only=True)
    assert len(classeur.worksheets) == 1, classeur.sheetnames
    return [tuple(ligne) for ligne in classeur.worksheets[0].iter_rows(values_only=True)]


def _vide(valeur: Any) -> bool:
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _titre_entete_lignes(lignes: list[tuple[Any, ...]]) -> tuple[str, list[Any], list[tuple[Any, ...]]]:
    """Titre (ligne 1), en-tête (première ligne non vide suivante), lignes de données ensuite."""
    non_vides = [ligne for ligne in lignes if not all(_vide(c) for c in ligne)]
    assert len(non_vides) >= 2, lignes
    titre = " ".join(str(c) for c in non_vides[0] if not _vide(c))
    entete = [c for c in non_vides[1]]
    while entete and _vide(entete[-1]):
        entete.pop()
    donnees = [tuple(ligne[: len(entete)]) for ligne in non_vides[2:]]
    return titre, entete, donnees


@pytest.mark.parametrize("niveau", ["poste_source", "feeder"])
async def test_export_entetes_http(client_suivi: AsyncClient, niveau: str) -> None:
    response = await _export(client_suivi, _make_user("ADMIN_SAQS"), {"niveau": niveau})
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment"), disposition
    assert f'filename="suivi_{niveau}_2026-11-14_2026-11-20.xlsx"' in disposition, disposition


async def test_export_feeder_contenu(client_suivi: AsyncClient) -> None:
    """Titre, en-tête du niveau feeder (avec Poste source), lignes de /reseau dans le même ordre."""
    user = _make_user("ADMIN_SAQS")
    reseau = await _ok(client_suivi, user, {"niveau": "feeder"})
    titre, entete, donnees = _titre_entete_lignes(_feuille((await _export(client_suivi, user, {"niveau": "feeder"})).content))
    assert titre.strip(), "ligne de titre vide"
    assert entete == [
        "Feeder", "Code", "Poste source", "Interruptions", "Durée (h)", "END (MWh)",
        "Coupures-clients", "Postes touchés", "Part (%)",
    ]
    assert len(donnees) == len(reseau["lignes"]) == 5
    for ligne_xlsx, ligne_api in zip(donnees, reseau["lignes"]):
        libelle, code, poste_source, nombre, duree, end, clients, postes, part = ligne_xlsx
        assert libelle == ligne_api["libelle"]
        assert (code if not _vide(code) else None) == ligne_api["code"]
        assert (poste_source if not _vide(poste_source) else None) == ligne_api["poste_source"]
        assert nombre == ligne_api["nombre"]
        assert duree == pytest.approx(ligne_api["duree_heures"], **APPROX)
        assert end == pytest.approx(ligne_api["end_mwh"], **APPROX)
        assert clients == ligne_api["coupures_clients"]
        assert postes == ligne_api["postes_touches"]
        assert part == pytest.approx(100 * ligne_api["part"], abs=0.1)
    assert donnees[0][:3] == ("BEL AIR 2", "F-BELAIR-2", "SOCOCIM")
    assert donnees[-1][0] == "Non renseigné"


async def test_export_poste_source_contenu(client_suivi: AsyncClient) -> None:
    """Niveau poste_source : pas de colonne Poste source en plus."""
    user = _make_user("ADMIN_SAQS")
    titre, entete, donnees = _titre_entete_lignes(
        _feuille((await _export(client_suivi, user, {"niveau": "poste_source"})).content)
    )
    assert titre.strip()
    assert entete == [
        "Poste source", "Code", "Interruptions", "Durée (h)", "END (MWh)",
        "Coupures-clients", "Postes touchés", "Part (%)",
    ]
    assert [(d[0], d[2]) for d in donnees] == [("HANN", 3), ("SOCOCIM", 2), ("KAOLACK", 1), ("Non renseigné", 3)]
    hann = donnees[0]
    assert hann[1] == "PS-HANN"
    assert hann[3] == pytest.approx(195 / 60, **APPROX)
    assert hann[4] == pytest.approx(3.2, **APPROX)
    assert (hann[5], hann[6]) == (1600, 3)
    assert hann[7] == pytest.approx(100 / 3, abs=0.1)


async def test_export_toutes_les_lignes(client_suivi: AsyncClient) -> None:
    _, _, donnees = _titre_entete_lignes(
        _feuille((await _export(client_suivi, _make_user("ADMIN_SAQS"), {**MARS, "niveau": "feeder"})).content)
    )
    assert [d[0] for d in donnees] == [f"MARS DEPART {n}" for n in range(10, 22)]


async def test_export_periode_vide_en_tete_seul(client_suivi: AsyncClient) -> None:
    response = await _export(
        client_suivi, _make_user("ADMIN_SAQS"), {"niveau": "feeder", "debut": "2026-12-05", "fin": "2026-12-11"}
    )
    assert 'filename="suivi_feeder_2026-12-05_2026-12-11.xlsx"' in response.headers["content-disposition"]
    _, entete, donnees = _titre_entete_lignes(_feuille(response.content))
    assert entete[0] == "Feeder"
    assert donnees == []


@pytest.mark.parametrize("role", ["BCC", "BRC"])
async def test_export_regional_limite_a_sa_region(client_suivi: AsyncClient, role: str) -> None:
    _, _, donnees = _titre_entete_lignes(
        _feuille((await _export(client_suivi, _make_user(role, scope_service_id=2), {"niveau": "poste_source"})).content)
    )
    assert [(d[0], d[2]) for d in donnees] == [("KAOLACK", 1), ("Non renseigné", 2)]


async def test_export_superviseur_limite_a_son_service(client_suivi: AsyncClient) -> None:
    _, _, donnees = _titre_entete_lignes(
        _feuille((await _export(client_suivi, _make_user("SUPERVISEUR", scope_service_id=1), {"niveau": "feeder"})).content)
    )
    assert [(d[0], d[3]) for d in donnees] == [("HANN DEPART 1", 2), ("HANN DEPART 2", 1)]
