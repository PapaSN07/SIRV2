"""Jeu de données SQLite commun aux tests d'API « Suivi incidents » (Vue d'ensemble, Classement).

Les tables sont créées avec toutes les colonnes des modèles SQLAlchemy (sans type : SQLite
accepte tout), pour que l'implémentation puisse lire n'importe quelle colonne. Cache Redis :
fakeredis vidé à chaque test. Utilisateur : ``utilisateur_repository.get_by_id`` patché.

Période principale : semaine SENELEC S47 2026 (samedi 14/11 → vendredi 20/11/2026).
Période précédente : S46 (07/11 → 13/11/2026).

Référentiel
- régions : 1 DAKAR, 2 REGIONS
- services : 1 SDDV « Service Dakar Ville » (Dakar), 2 SDPG « Service Pikine Guediawaye » (Dakar),
  3 DRS « Direction Regionale Sud » (Régions)
- postes sources : 1 HANN, 2 SOCOCIM, 3 KAOLACK
- feeders : 1 « HANN DEPART 1 » (PS 1), 2 « HANN DEPART 2 » (PS 1), 3 « BEL AIR 2 » (PS 2),
  4 « KAOLACK VILLE » (PS 3)
- natures : 1 PERMANENT, 2 FUGITIF, 3 DELESTAGE, 4 COUPURE, 5 SEMI PERMANENT
- causes : 1 « Défaut câble HTA », 2 « Défaut réseau HTB » (HTB), 3 « Travaux d'entretien »,
  4 « Choc accidentel » (exogène), 5 « Manœuvre réseau », 6 « MANQUE PRODUCTION » (HTB)
- postes : 1 à 6

Interruptions distribution de S47 (tous statuts) :

| id  | rég | svc | PS | feeder | nature | cause    | durée | clients | END  | postes | catégorie | réseau |
|-----|-----|-----|----|--------|--------|----------|-------|---------|------|--------|-----------|--------|
| 101 | 1   | 1   | 1  | 1      | PERM   | 1        | 120   | 1000    | 2.5  | P1, P2 | incident  | hta    |
| 102 | 1   | 1   | 1  | 2      | FUG    | 4 (exo)  | 30    | 500     | 0.5  | P2, P3 | incident  | hta    |
| 103 | 1   | 2   | 2  | 3      | DEL    | 6 (PROD) | 60    | 2000    | 4.0  | P4     | delestage | htb    |
| 104 | 2   | 3   | 3  | 4      | COUP   | 3 (trav) | 240   | 300     | 1.0  | P5     | travaux   | hta    |
| 105 | 2   | 3   | —  | —      | COUP   | 5 (manœ) | —     | —       | —    | —      | autre     | hta    |
| 106 | 1   | 2   | 2  | 3      | PERM   | 2 (HTB)  | 90    | 800     | 1.5  | P4     | autre     | htb    |
| 107 | 1   | 1   | 1  | 1      | SEMI   | —        | 45    | 100     | 0.2  | P1     | incident  | hta    |
| 108 | 1   | —   | —  | —      | —      | —        | 10    | 50      | 0.1  | —      | autre     | hta    |
| 109 | 2   | 3   | —  | —      | FUG    | 1        | 15    | 20      | 0.05 | —      | incident  | hta    |

105 : en cours, durée, clients et END non renseignés (pas de ligne interruptions_distribution).
Hors S47 : 201 transport (S47, ignorée), 203 le 21/11 à 0 h, 205 le 06/11 (avant S46).
S46 : 202 (13/11 23 h, Dakar, SDDV, PS 1, F1, 60 min, 400 clients, 0.8 MWh, P1) et
204 (07/11 0 h, Régions, DRS, PS 3, F4, 20 min, 100 clients, 0.1 MWh, sans poste).

Ajouts de l'étape 4 (Évolution, Réseau), hors des périodes lues par les tests de l'étape 3
(S46, S47, 13/11 → 16/11, 05/12 → 11/12) :

- feeder 5 « DEPART ISOLE » (F-ISOLE) **sans poste source** ; feeders 10 à 21 « MARS DEPART 10 »
  à « MARS DEPART 21 » (F-M10 … F-M21, poste source HANN).

| id  | apparition       | rég | svc | PS | feeder | nature | cause    | durée | clients | END  | postes | catégorie |
|-----|------------------|-----|-----|----|--------|--------|----------|-------|---------|------|--------|-----------|
| 301 | 10/08/2026 10:00 | 1   | 1   | 1  | 1      | PERM   | 1        | 60    | 100     | 0.3  | P1     | incident  |
| 302 | 31/08/2026 23:30 | 2   | 3   | 3  | 4      | DEL    | 1        | 30    | 200     | 0.4  | P5     | delestage |
| 303 | 01/09/2026 00:00 | 1   | 2   | 2  | 3      | COUP   | 3 (trav) | 120   | 50      | 0.6  | P4     | travaux   |
| 304 | 03/10/2026 10:00 | 1   | 1   | —  | 1      | PERM   | 1        | 60    | 100     | 0.3  | P1, P2 | incident  |
| 305 | 10/10/2026 08:00 | 1   | 1   | —  | 5      | FUG    | 4 (exo)  | 30    | 200     | 0.4  | P6     | incident  |
| 306 | 10/10/2026 09:00 | 1   | 1   | —  | 5      | FUG    | 4 (exo)  | 10    | 30      | 0.1  | P6     | incident  |
| 307 | 31/12/2026 22:00 | 1   | 1   | 1  | 2      | PERM   | 2 (HTB)  | 45    | 300     | 0.9  | P3     | autre     |
| 308 | 02/01/2027 06:00 | 2   | 3   | 3  | 4      | DEL    | 6 (PROD) | 20    | 400     | 0.5  | P5     | delestage |
| 309 | 08/01/2027 12:00 | 1   | 2   | 2  | 3      | COUP   | 5 (manœ) | 15    | 60      | 0.05 | P4     | autre     |
| 310 à 321 | 10/03/2026 08:00 | 1 | 1 | 1 | 10 à 21 | PERM | 1     | 10    | 10      | 0.01 | —      | incident  |

304 à 306 : poste source de l'interruption non renseigné (le feeder, lui, en a un ou non).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from tests.integration.test_api_suivi_incidents_filtres import _headers, _make_user  # noqa: F401

SEMAINE = {"debut": "2026-11-14", "fin": "2026-11-20"}
SEMAINE_PRECEDENTE = {"debut": "2026-11-07", "fin": "2026-11-13"}


def _modeles() -> list[Any]:
    from app.models.geo import Region, Service
    from app.models.interruptions import (
        Interruption,
        InterruptionDistribution,
        InterruptionTransport,
        PosteInterruption,
    )
    from app.models.referentiel import Cause, Nature
    from app.models.reseau import Feeder, Poste, PosteSource

    return [
        Region, Service, PosteSource, Feeder, Poste, Nature, Cause,
        Interruption, InterruptionDistribution, InterruptionTransport, PosteInterruption,
    ]


def _ddl(modele: Any) -> str:
    table = modele.__table__
    colonnes = ", ".join(
        "id INTEGER PRIMARY KEY" if c.name == "id" else c.name for c in table.columns
    )
    return f"CREATE TABLE {table.name} ({colonnes})"


def _d(texte: str) -> str:
    """Date au format écrit par SQLAlchemy pour SQLite (comparaisons texte cohérentes)."""
    return f"{texte}.000000"


# (id, type_direction, statut, apparition, région, service, poste source, feeder, nature, cause,
#  durée minutes, clients, END MWh | None = pas de ligne interruptions_distribution, postes)
_INTERRUPTIONS: list[tuple[Any, ...]] = [
    (101, "distribution", "valide", "2026-11-14 08:00:00", 1, 1, 1, 1, 1, 1, 120, 1000, 2.5, [1, 2]),
    (102, "distribution", "cloture", "2026-11-15 09:00:00", 1, 1, 1, 2, 2, 4, 30, 500, 0.5, [2, 3]),
    (103, "distribution", "en_cours", "2026-11-16 10:00:00", 1, 2, 2, 3, 3, 6, 60, 2000, 4.0, [4]),
    (104, "distribution", "valide", "2026-11-17 11:00:00", 2, 3, 3, 4, 4, 3, 240, 300, 1.0, [5]),
    (105, "distribution", "en_cours", "2026-11-18 12:00:00", 2, 3, None, None, 4, 5, None, None, None, []),
    (106, "distribution", "archive", "2026-11-19 13:00:00", 1, 2, 2, 3, 1, 2, 90, 800, 1.5, [4]),
    (107, "distribution", "brouillon", "2026-11-20 23:59:00", 1, 1, 1, 1, 5, None, 45, 100, 0.2, [1]),
    (108, "distribution", "valide", "2026-11-14 00:00:00", 1, None, None, None, None, None, 10, 50, 0.1, []),
    (109, "distribution", "valide", "2026-11-17 15:00:00", 2, 3, None, None, 2, 1, 15, 20, 0.05, []),
    # --- hors période ou hors distribution ---
    (201, "transport", "valide", "2026-11-16 10:00:00", 1, 1, 1, 1, 1, 1, 500, 9999, None, [6]),
    (203, "distribution", "valide", "2026-11-21 00:00:00", 1, 1, 1, 1, 1, 1, 100, 100, 1.0, [6]),
    (205, "distribution", "valide", "2026-11-06 23:59:00", 1, 1, 1, 1, 1, 1, 100, 100, 1.0, [6]),
    # --- semaine précédente (S46) ---
    (202, "distribution", "valide", "2026-11-13 23:00:00", 1, 1, 1, 1, 1, 1, 60, 400, 0.8, [1]),
    (204, "distribution", "valide", "2026-11-07 00:00:00", 2, 3, 3, 4, 2, 1, 20, 100, 0.1, []),
    # --- étape 4 : autres mois, changement d'année, feeders sans poste source ---
    (301, "distribution", "valide", "2026-08-10 10:00:00", 1, 1, 1, 1, 1, 1, 60, 100, 0.3, [1]),
    (302, "distribution", "valide", "2026-08-31 23:30:00", 2, 3, 3, 4, 3, 1, 30, 200, 0.4, [5]),
    (303, "distribution", "valide", "2026-09-01 00:00:00", 1, 2, 2, 3, 4, 3, 120, 50, 0.6, [4]),
    (304, "distribution", "valide", "2026-10-03 10:00:00", 1, 1, None, 1, 1, 1, 60, 100, 0.3, [1, 2]),
    (305, "distribution", "cloture", "2026-10-10 08:00:00", 1, 1, None, 5, 2, 4, 30, 200, 0.4, [6]),
    (306, "distribution", "valide", "2026-10-10 09:00:00", 1, 1, None, 5, 2, 4, 10, 30, 0.1, [6]),
    (307, "distribution", "valide", "2026-12-31 22:00:00", 1, 1, 1, 2, 1, 2, 45, 300, 0.9, [3]),
    (308, "distribution", "valide", "2027-01-02 06:00:00", 2, 3, 3, 4, 3, 6, 20, 400, 0.5, [5]),
    (309, "distribution", "en_cours", "2027-01-08 12:00:00", 1, 2, 2, 3, 4, 5, 15, 60, 0.05, [4]),
    *[
        (300 + n, "distribution", "valide", "2026-03-10 08:00:00", 1, 1, 1, n, 1, 1, 10, 10, 0.01, [])
        for n in range(10, 22)
    ],
]


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
        "(5, NULL, 1, 1, 'F-ISOLE', 'DEPART ISOLE', 1), "
        + ", ".join(f"({n}, 1, 1, 1, 'F-M{n}', 'MARS DEPART {n}', 1)" for n in range(10, 22)),
        "INSERT INTO postes (id, feeder_id, service_id, code, libelle, nombre_clients, is_active) VALUES "
        "(1, 1, 1, 'P1', 'POSTE 1', 600, 1), (2, 1, 1, 'P2', 'POSTE 2', 400, 1), "
        "(3, 2, 1, 'P3', 'POSTE 3', 100, 1), (4, 3, 2, 'P4', 'POSTE 4', 2000, 1), "
        "(5, 4, 3, 'P5', 'POSTE 5', 300, 1), (6, 1, 1, 'P6', 'POSTE 6', 50, 1)",
        "INSERT INTO natures (id, code, libelle, is_active) VALUES "
        "(1, 'PERM', 'PERMANENT', 1), (2, 'FUG', 'FUGITIF', 1), (3, 'DEL', 'DELESTAGE', 1), "
        "(4, 'COUP', 'COUPURE', 1), (5, 'SEMI', 'SEMI PERMANENT', 1)",
        "INSERT INTO causes (id, code, libelle, type_reseau, is_active, est_exogene) VALUES "
        "(1, 'C1', 'Défaut câble HTA', 'distribution', 1, 0), "
        "(2, 'C2', 'Défaut réseau HTB', 'distribution', 1, 0), "
        "(3, 'C3', 'Travaux d''entretien', 'distribution', 1, 0), "
        "(4, 'C4', 'Choc accidentel', 'distribution', 1, 1), "
        "(5, 'C5', 'Manœuvre réseau', 'distribution', 1, 0), "
        "(6, 'C6', 'MANQUE PRODUCTION', 'distribution', 1, 0)",
    ]
    poste_id = 1
    for (
        iid, direction, statut, apparition, region, service, ps, feeder, nature, cause,
        duree, clients, end, postes,
    ) in _INTERRUPTIONS:
        def v(x: Any) -> str:
            return "NULL" if x is None else repr(x)

        lignes.append(
            "INSERT INTO interruptions (id, numero_interruption, type_direction, direction_source_id, statut, "
            "statut_id, region_id, service_id, poste_source_id, feeder_id, nature_id, cause_id, "
            "date_apparition, date_remise, duree_minutes, nombre_clients_touches, is_force_majeure, "
            "is_fugitive, created_by_id) VALUES "
            f"({iid}, {iid}, '{direction}', 1, '{statut}', 1, {v(region)}, {v(service)}, {v(ps)}, "
            f"{v(feeder)}, {v(nature)}, {v(cause)}, '{_d(apparition)}', NULL, {v(duree)}, {v(clients)}, "
            "0, 0, 1)"
        )
        if direction == "distribution" and end is not None:
            lignes.append(
                "INSERT INTO interruptions_distribution (id, interruption_id, end_mwh, is_programme, "
                f"has_extension_bt) VALUES ({iid}, {iid}, {end}, 0, 0)"
            )
        if direction == "transport":
            lignes.append(
                "INSERT INTO interruptions_transport (id, interruption_id, energie_non_fournie_mwh) "
                f"VALUES ({iid}, {iid}, 50.0)"
            )
        # clients des postes : la somme par interruption vaut nombre_clients_touches
        for rang, p in enumerate(postes):
            part = None if clients is None else (clients if rang == 0 else 0)
            lignes.append(
                "INSERT INTO poste_interruptions (id, interruption_id, poste_id, feeder_id, service_id, "
                "poste_source_id, nombre_clients_touches, nombre_clients_estime) VALUES "
                f"({poste_id}, {iid}, {p}, {v(feeder)}, {v(service)}, {v(ps)}, {v(part)}, {v(part)})"
            )
            poste_id += 1
    return lignes


@pytest_asyncio.fixture
async def session_suivi() -> AsyncIterator[AsyncSession]:
    """Base SQLite en mémoire remplie du jeu de données ci-dessus."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"dbo": None}},
    )
    async with engine.begin() as connexion:
        for modele in _modeles():
            await connexion.exec_driver_sql(_ddl(modele))
        for ordre in _inserts():
            await connexion.exec_driver_sql(ordre)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client_suivi(session_suivi: AsyncSession, fake_redis: Any) -> AsyncIterator[AsyncClient]:
    """Client HTTP de l'application : base SQLite ci-dessus, Redis fakeredis vidé."""
    from app.core.database import get_db
    from app.core.redis import get_redis
    from app.main import app

    await fake_redis.flushall()

    async def _db() -> AsyncIterator[AsyncSession]:
        yield session_suivi

    async def _redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = _redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


async def appeler(client: AsyncClient, url: str, user: Any, params: dict[str, Any] | None = None):
    """GET authentifié ; l'utilisateur est renvoyé par le repository patché."""
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user):
        return await client.get(url, params=params or {}, headers=_headers(user))


def erreur_enveloppee(corps: Any) -> dict[str, Any]:
    """Enveloppe d'erreur {"status": "error", "data": None, "error": "..."} (à la racine ou dans
    ``detail`` d'une HTTPException) ; la liste brute de FastAPI n'est pas acceptée."""
    enveloppe = corps.get("detail", corps) if isinstance(corps, dict) else corps
    assert isinstance(enveloppe, dict), f"erreur non enveloppée : {corps!r}"
    assert enveloppe.get("status") == "error", corps
    assert enveloppe.get("data") is None, corps
    assert isinstance(enveloppe.get("error"), str) and enveloppe["error"].strip(), corps
    return enveloppe
