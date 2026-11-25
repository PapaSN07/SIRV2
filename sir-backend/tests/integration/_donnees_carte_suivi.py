"""Jeu de données SQLite des onglets Carte et Localisation du « Suivi incidents » (étape 6a, §11).

Jeu **séparé** de ``_donnees_suivi_incidents.py`` et ``_donnees_saifi_suivi.py`` (rien n'y est
modifié) : il ajoute les nœuds SIG et les lignes ``schema_unifilaire_postes``. Tables, DDL et
utilitaires d'appel repris de ``_donnees_suivi_incidents.py``.

Période principale : semaine SENELEC S47 2026 (samedi 14/11 → vendredi 20/11/2026).

Référentiel
- régions : 1 DAKAR, 2 REGIONS ; services : 1 SDDV (Dakar), 2 SDPG (Dakar), 3 DRS (Régions)
- postes sources : 1 HANN, 2 SOCOCIM, 3 KAOLACK
- feeders : 1 « HANN DEPART 1 » (PS 1), 2 « HANN DEPART 2 » (PS 1), 3 « BEL AIR 2 » (PS 2),
  4 « KAOLACK VILLE » (PS 3), 5 « DEPART ISOLE » (**sans poste source** : colonne NOT NULL dans le
  modèle, mais le cas est traité comme à l'étape 4)
- natures : 1 PERMANENT, 2 FUGITIF, 3 DELESTAGE, 4 COUPURE
- causes : 1 « Défaut câble HTA », 3 « Travaux d'entretien », 5 « Manœuvre réseau »

Postes et localisation attendue (coordonnées en degrés : x = longitude, y = latitude, sauf N102
en UTM 28N, converti par ``pilotage_repository._lon_lat``) :

| poste | code     | libellé | feeder | localisation | point attendu | pourquoi |
|-------|----------|---------|--------|--------------|---------------|----------|
| 1     | P-ALPHA  | ALPHA   | 1      | rapprochement | (-17.40, 14.70) N104 | ligne 1 ambiguë (plus petite id) ignorée, ligne 4 auto ; le nœud « ALPHA » N201 (nom) n'est pas pris |
| 2     | P-BRAVO  | BRAVO   | 1      | rapprochement | UTM (237000, 1627000) → (-17.442363, 14.703901) N102 | lignes 2 (manuel) et 5 (auto) : la plus petite id |
| 3     | P-CHARLIE| CHARLIE | 2      | nom | (-17.30, 14.75) N202 | ligne 3 ambiguë ignorée |
| 4     | P-DELTA  | DELTA   | 3      | non localisé | — | ligne 6 auto vers N106 inactif (nommé DELTA, inactif aussi pour le nom) |
| 5     | P-ECHO   | ECHO    | 3      | nom | (-16.90, 14.80) N203 | ligne 7 auto vers N107 hors emprise (0, 0) |
| 6     | P-FOX    | FOXTROT | 4      | nom | (-16.07, 14.15) N204 | homonymes éloignés (F4, F1) départagés par le feeder **du poste** ; le nœud « P-FOX » (code) n'est pas pris : libellé d'abord |
| 7     | P-GOLF   | GOLF    | —      | non localisé | — | homonymes éloignés, poste sans feeder |
| 8     | P-HOTEL  | HOTEL   | —      | nom | ≈ (-17.350, 14.720) | homonymes proches (< 0,01°) |
| 9     | P-INDIA9 | INDIA   | 5      | nom | (-17.20, 14.65) N210 | libellé introuvable, code trouvé |
| 10    | P-JULIET | JULIET  | 2      | non localisé | — | seul nœud « JULIET » inactif |
| 11    | P-KILO   | KILO    | 4      | non localisé | — | ligne 8 sans nœud ; nœud « KILO » hors emprise |
| 12    | P-LIMA   | LIMA    | —      | non localisé | — | ligne 10 auto vers N109 sans coordonnées ; pas de nœud « LIMA » |
| 13    | P-MIKE   | MIKE    | 4      | non localisé | — | homonymes éloignés sur F1 et F3, aucun sur F4 |

Interruptions distribution de S47 (postes : (poste, clients estimés, clients touchés)) :

| id  | statut   | apparition       | rég | svc | PS | F | nature | cause | durée | postes | catégorie |
|-----|----------|------------------|-----|-----|----|---|--------|-------|-------|--------|-----------|
| 601 | valide   | 14/11 08:00      | 1   | 1   | 1  | 1 | PERM   | 1     | 60    | (1, 100, 90), (2, 200, 200) | incident |
| 602 | cloture  | 15/11 09:00      | 1   | 1   | 1  | 1 | DEL    | 1     | 30    | (1, 50, 50), (3, —, 40) | delestage |
| 603 | en_cours | 16/11 10:00      | 1   | 1   | 1  | 1 | PERM   | 1     | —     | (1, —, —) | incident |
| 604 | valide   | 17/11 11:00      | 1   | 2   | 2  | 3 | COUP   | 3     | 120   | (4, 300, 300), (5, 10, 10) | travaux |
| 605 | archive  | 18/11 12:00      | 1   | 2   | 2  | 3 | COUP   | 5     | 45    | (5, 20, 20), (4, 5, 5) | autre |
| 606 | valide   | 19/11 08:00      | 2   | 3   | 3  | 4 | PERM   | 1     | 90    | (6, 500, 500), (11, 0, 0), (13, 40, 40) | incident |
| 607 | valide   | 19/11 12:00      | 2   | 3   | 3  | 4 | DEL    | 1     | 15    | (6, 100, 100) | delestage |
| 608 | valide   | 20/11 23:59      | 1   | 1   | —  | — | PERM   | 1     | 10    | (7, 5, 5), (8, 6, 6), (9, 7, 7), (12, 3, 3) | incident |
| 609 | brouillon| 20/11 10:00      | 1   | 1   | —  | — | COUP   | 3     | 20    | (8, 4, 4) | travaux |
| 610 | valide   | 17/11 15:00      | 1   | 1   | 1  | 2 | DEL    | 1     | 25    | (3, 30, 30), (10, 1, 1) | delestage |

Hors S47 : 620 transport (16/11, P1, 9 999 clients), 621 distribution le 21/11 à 0 h (P1),
622 distribution le 13/11 à 23:59 (P2). ``interruptions.nombre_clients_touches`` vaut 7777 partout
(pour détecter une lecture de la mauvaise colonne).

Résultats attendus en national sur S47 (postes touchés 13, localisés 7 : rapprochement 2, nom 5) :

| poste   | nombre | durée (h) | clients | nature dominante |
|---------|--------|-----------|---------|------------------|
| ALPHA   | 3      | 1.5       | 150     | incident (2 contre 1) |
| BRAVO   | 1      | 1.0       | 200     | incident |
| CHARLIE | 2      | 55/60     | 70      | delestage |
| DELTA   | 2      | 2.75      | 305     | travaux (égalité travaux / autre) |
| ECHO    | 2      | 2.75      | 30      | travaux (égalité travaux / autre) |
| FOXTROT | 2      | 1.75      | 600     | incident (égalité incident / délestage) |
| GOLF    | 1      | 10/60     | 5       | incident |
| HOTEL   | 2      | 0.5       | 10      | incident (égalité incident / travaux) |
| INDIA   | 1      | 10/60     | 7       | incident |
| JULIET  | 1      | 25/60     | 1       | delestage |
| KILO    | 1      | 1.5       | 0       | incident |
| LIMA    | 1      | 10/60     | 3       | incident |
| MIKE    | 1      | 1.5       | 40      | incident |
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from tests.integration._donnees_suivi_incidents import (  # noqa: F401 (réexportés)
    _d,
    _ddl,
    _make_user,
    _modeles,
    appeler,
    erreur_enveloppee,
)

SEMAINE = {"debut": "2026-11-14", "fin": "2026-11-20"}
PERIODE_VIDE = {"debut": "2025-01-01", "fin": "2025-01-31"}

# Coordonnées attendues (longitude, latitude)
POINT_ALPHA = (-17.40, 14.70)
POINT_BRAVO = (-17.442363416605, 14.703901116809)  # UTM 28N (237000, 1627000), référence pyproj
POINT_CHARLIE = (-17.30, 14.75)
POINT_ECHO = (-16.90, 14.80)
POINT_FOXTROT = (-16.07, 14.15)
POINT_HOTEL = (-17.35, 14.72)
POINT_INDIA = (-17.20, 14.65)

# (id, code, libellé, feeder)
POSTES: list[tuple[int, str, str, int | None]] = [
    (1, "P-ALPHA", "ALPHA", 1),
    (2, "P-BRAVO", "BRAVO", 1),
    (3, "P-CHARLIE", "CHARLIE", 2),
    (4, "P-DELTA", "DELTA", 3),
    (5, "P-ECHO", "ECHO", 3),
    (6, "P-FOX", "FOXTROT", 4),
    (7, "P-GOLF", "GOLF", None),
    (8, "P-HOTEL", "HOTEL", None),
    (9, "P-INDIA9", "INDIA", 5),
    (10, "P-JULIET", "JULIET", 2),
    (11, "P-KILO", "KILO", 4),
    (12, "P-LIMA", "LIMA", None),
    (13, "P-MIKE", "MIKE", 4),
]

# Nœuds SIG : (id, nom, feeder, x, y, actif)
NOEUDS: list[tuple[int, str, int | None, float | None, float | None, int]] = [
    # --- nœuds des lignes de rapprochement ---
    (101, "SCHEMA ALPHA AMBIGU", 1, -16.00, 13.00, 1),
    (102, "SCHEMA BRAVO", 1, 237000.0, 1627000.0, 1),
    (103, "SCHEMA CHARLIE AMBIGU", 2, -17.00, 14.00, 1),
    (104, "SCHEMA ALPHA", 1, -17.40, 14.70, 1),
    (105, "SCHEMA BRAVO BIS", 1, -16.50, 14.40, 1),
    (106, "DELTA", 3, -17.38, 14.69, 0),
    (107, "ECHO", 3, 0.0, 0.0, 1),
    (108, "SCHEMA SANS POSTE", 1, -17.41, 14.71, 1),
    (109, "SCHEMA LIMA", None, None, None, 1),
    # --- nœuds trouvés par le nom ---
    (201, "ALPHA", 1, -17.10, 14.60, 1),
    (202, "CHARLIE", 2, -17.30, 14.75, 1),
    (203, "ECHO", 3, -16.90, 14.80, 1),
    (204, "FOXTROT", 4, -16.07, 14.15, 1),
    (205, "FOXTROT", 1, -17.45, 14.70, 1),
    (206, "GOLF", 1, -17.45, 14.70, 1),
    (207, "GOLF", 3, -16.50, 14.40, 1),
    (208, "HOTEL", None, -17.3500, 14.7200, 1),
    (209, "HOTEL", None, -17.3502, 14.7201, 1),
    (210, "P-INDIA9", 5, -17.20, 14.65, 1),
    (211, "MIKE", 1, -17.45, 14.70, 1),
    (212, "MIKE", 3, -16.50, 14.40, 1),
    (213, "JULIET", 2, -17.00, 14.50, 0),
    (214, "KILO", 4, 500.0, 500.0, 1),
    (215, "P-FOX", 4, -15.50, 13.50, 1),
]

# Lignes schema_unifilaire_postes : (id, poste, nœud, rapprochement_sig)
RAPPROCHEMENTS: list[tuple[int, int | None, int | None, str | None]] = [
    (5, 2, 105, "auto"),  # insérée avant la ligne 2 : la plus petite id doit gagner quand même
    (1, 1, 101, "ambigu"),
    (2, 2, 102, "manuel"),
    (3, 3, 103, "ambigu"),
    (4, 1, 104, "auto"),
    (6, 4, 106, "auto"),
    (7, 5, 107, "auto"),
    (8, 11, None, None),
    (9, None, 108, "auto"),
    (10, 12, 109, "auto"),
]

# (id, direction, statut, apparition, région, service, PS, feeder, nature, cause, durée, postes)
_INTERRUPTIONS: list[tuple[Any, ...]] = [
    (601, "distribution", "valide", "2026-11-14 08:00:00", 1, 1, 1, 1, 1, 1, 60, [(1, 100, 90), (2, 200, 200)]),
    (602, "distribution", "cloture", "2026-11-15 09:00:00", 1, 1, 1, 1, 3, 1, 30, [(1, 50, 50), (3, None, 40)]),
    (603, "distribution", "en_cours", "2026-11-16 10:00:00", 1, 1, 1, 1, 1, 1, None, [(1, None, None)]),
    (604, "distribution", "valide", "2026-11-17 11:00:00", 1, 2, 2, 3, 4, 3, 120, [(4, 300, 300), (5, 10, 10)]),
    (605, "distribution", "archive", "2026-11-18 12:00:00", 1, 2, 2, 3, 4, 5, 45, [(5, 20, 20), (4, 5, 5)]),
    (606, "distribution", "valide", "2026-11-19 08:00:00", 2, 3, 3, 4, 1, 1, 90, [(6, 500, 500), (11, 0, 0), (13, 40, 40)]),
    (607, "distribution", "valide", "2026-11-19 12:00:00", 2, 3, 3, 4, 3, 1, 15, [(6, 100, 100)]),
    (608, "distribution", "valide", "2026-11-20 23:59:00", 1, 1, None, None, 1, 1, 10, [(7, 5, 5), (8, 6, 6), (9, 7, 7), (12, 3, 3)]),
    (609, "distribution", "brouillon", "2026-11-20 10:00:00", 1, 1, None, None, 4, 3, 20, [(8, 4, 4)]),
    (610, "distribution", "valide", "2026-11-17 15:00:00", 1, 1, 1, 2, 3, 1, 25, [(3, 30, 30), (10, 1, 1)]),
    # --- hors période ou hors distribution ---
    (620, "transport", "valide", "2026-11-16 10:00:00", 1, 1, 1, 1, 1, 1, 500, [(1, 9999, 9999)]),
    (621, "distribution", "valide", "2026-11-21 00:00:00", 1, 1, 1, 1, 1, 1, 100, [(1, 1000, 1000)]),
    (622, "distribution", "valide", "2026-11-13 23:59:00", 1, 1, 1, 1, 1, 1, 100, [(2, 1000, 1000)]),
]


def _modeles_carte() -> list[Any]:
    from app.models.schema_unifilaire import SchemaUnifilaire, SchemaUnifilairePoste
    from app.models.sig import NoeudSig

    return [*_modeles(), NoeudSig, SchemaUnifilaire, SchemaUnifilairePoste]


def _v(x: Any) -> str:
    return "NULL" if x is None else repr(x)


def _inserts() -> list[str]:
    lignes = [
        "INSERT INTO regions (id, code, libelle, is_active) VALUES (1, 'DKR', 'DAKAR', 1), (2, 'REG', 'REGIONS', 1)",
        "INSERT INTO services (id, agence_id, region_id, code, libelle, is_active) VALUES "
        "(1, 1, 1, 'SDDV', 'Service Dakar Ville', 1), "
        "(2, 1, 1, 'SDPG', 'Service Pikine Guediawaye', 1), "
        "(3, 2, 2, 'DRS', 'Direction Regionale Sud', 1)",
        "INSERT INTO postes_sources (id, code, libelle, region_id, is_active) VALUES "
        "(1, 'PS-HANN', 'HANN', 1, 1), (2, 'PS-SOC', 'SOCOCIM', 1, 1), (3, 'PS-KAO', 'KAOLACK', 2, 1)",
        "INSERT INTO feeders (id, poste_source_id, service_id, region_id, code, libelle, is_active) VALUES "
        "(1, 1, 1, 1, 'F-HANN-1', 'HANN DEPART 1', 1), "
        "(2, 1, 1, 1, 'F-HANN-2', 'HANN DEPART 2', 1), "
        "(3, 2, 2, 1, 'F-BELAIR-2', 'BEL AIR 2', 1), "
        "(4, 3, 3, 2, 'F-KAO-V', 'KAOLACK VILLE', 1), "
        "(5, NULL, 1, 1, 'F-ISOLE', 'DEPART ISOLE', 1)",
        "INSERT INTO postes (id, feeder_id, service_id, code, libelle, nombre_clients, is_active) VALUES "
        + ", ".join(f"({i}, {_v(f)}, 1, '{c}', '{l}', 100, 1)" for i, c, l, f in POSTES),
        "INSERT INTO natures (id, code, libelle, is_active) VALUES "
        "(1, 'PERM', 'PERMANENT', 1), (2, 'FUG', 'FUGITIF', 1), (3, 'DEL', 'DELESTAGE', 1), "
        "(4, 'COUP', 'COUPURE', 1)",
        "INSERT INTO causes (id, code, libelle, type_reseau, is_active, est_exogene) VALUES "
        "(1, 'C1', 'Défaut câble HTA', 'distribution', 1, 0), "
        "(3, 'C3', 'Travaux d''entretien', 'distribution', 1, 0), "
        "(5, 'C5', 'Manœuvre réseau', 'distribution', 1, 0)",
        "INSERT INTO noeuds_sig (id, legacy_id, legacy_fid, nom, feeder_id, coord_x, coord_y, source, est_actif) VALUES "
        + ", ".join(
            f"({i}, {i}, {i}, '{nom}', {_v(f)}, {_v(x)}, {_v(y)}, 'sir_v1', {actif})"
            for i, nom, f, x, y, actif in NOEUDS
        ),
        "INSERT INTO schemas_unifilaires (id, nom, fichier, region_id, largeur, hauteur, zoom_max, graphe, "
        "nb_postes, is_active) VALUES (1, 'SCHEMA TEST', 'schema.pdf', 1, 1000, 1000, 4, X'00', 10, 1)",
    ]
    for rang, (i, poste, noeud, mode) in enumerate(RAPPROCHEMENTS):
        lignes.append(
            "INSERT INTO schema_unifilaire_postes (id, schema_id, rang, libelle, forme, x0, y0, x1, y1, "
            "poste_id, rapprochement, noeud_sig_id, rapprochement_sig) VALUES "
            f"({i}, 1, {rang}, 'POSTE SCHEMA {i}', 'carre', 0, 0, 1, 1, {_v(poste)}, "
            f"{'NULL' if poste is None else repr('auto')}, {_v(noeud)}, {_v(mode)})"
        )
    poste_interruption_id = 1
    for iid, direction, statut, apparition, region, service, ps, feeder, nature, cause, duree, postes in _INTERRUPTIONS:
        lignes.append(
            "INSERT INTO interruptions (id, numero_interruption, type_direction, direction_source_id, statut, "
            "statut_id, region_id, service_id, poste_source_id, feeder_id, nature_id, cause_id, "
            "date_apparition, date_remise, duree_minutes, nombre_clients_touches, is_force_majeure, "
            "is_fugitive, created_by_id) VALUES "
            f"({iid}, {iid}, '{direction}', 1, '{statut}', 1, {_v(region)}, {_v(service)}, {_v(ps)}, "
            f"{_v(feeder)}, {_v(nature)}, {_v(cause)}, '{_d(apparition)}', NULL, {_v(duree)}, 7777, 0, 0, 1)"
        )
        if direction == "distribution":
            lignes.append(
                "INSERT INTO interruptions_distribution (id, interruption_id, end_mwh, is_programme, "
                f"has_extension_bt) VALUES ({iid}, {iid}, 0.1, 0, 0)"
            )
        else:
            lignes.append(
                "INSERT INTO interruptions_transport (id, interruption_id, energie_non_fournie_mwh) "
                f"VALUES ({iid}, {iid}, 50.0)"
            )
        for poste, estime, touches in postes:
            lignes.append(
                "INSERT INTO poste_interruptions (id, interruption_id, poste_id, feeder_id, service_id, "
                "poste_source_id, nombre_clients_touches, nombre_clients_estime) VALUES "
                f"({poste_interruption_id}, {iid}, {poste}, {_v(feeder)}, {_v(service)}, {_v(ps)}, "
                f"{_v(touches)}, {_v(estime)})"
            )
            poste_interruption_id += 1
    return lignes


@pytest_asyncio.fixture
async def session_carte() -> AsyncIterator[AsyncSession]:
    """Base SQLite en mémoire remplie du jeu Carte / Localisation ci-dessus."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"dbo": None}},
    )
    async with engine.begin() as connexion:
        for modele in _modeles_carte():
            await connexion.exec_driver_sql(_ddl(modele))
        for ordre in _inserts():
            await connexion.exec_driver_sql(ordre)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client_carte(session_carte: AsyncSession, fake_redis: Any) -> AsyncIterator[AsyncClient]:
    """Client HTTP de l'application : base SQLite Carte, Redis fakeredis vidé."""
    from app.core.database import get_db
    from app.core.redis import get_redis
    from app.main import app

    await fake_redis.flushall()

    async def _db() -> AsyncIterator[AsyncSession]:
        yield session_carte

    async def _redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = _redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
