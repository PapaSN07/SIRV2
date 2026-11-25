"""Jeu de données SQLite de l'onglet SAIFI / SAIDI du « Suivi incidents » (étape 5, §10).

Jeu **séparé** de ``_donnees_suivi_incidents.py`` : ce dernier n'a aucune ``date_remise`` (rien
n'y compte pour SAIFI / SAIDI) et des tests de l'étape 4 lisent des périodes de 2024 à 2027
entières ; y ajouter des interruptions les aurait cassés. Les tables, le DDL et les utilitaires
d'appel sont repris de ce module.

Référentiel
- régions : 1 DAKAR, 2 REGIONS
- services : 1 SDDV (Dakar), 2 SDPG (Dakar), 3 DRS (Régions), 4 SDRBD (Dakar, sans base clients)
- postes sources : 1 HANN, 2 SOCOCIM, 3 KAOLACK ; feeders : 1, 2 (PS 1), 3 (PS 2), 4 (PS 3)
- natures : 1 PERMANENT, 2 FUGITIF, 3 DELESTAGE, 4 COUPURE, 5 SEMI PERMANENT
- causes : 1 « Défaut câble HTA », 2 « Défaut réseau HTB » (HTB), 3 « Travaux d'entretien »,
  4 « Choc accidentel » (exogène), 5 « Manœuvre réseau », 6 « MANQUE PRODUCTION » (HTB)

Base clients ``nombre_client_mois`` (pas de photo en novembre ni avant août 2026) :

| mois     | SDDV (1) | SDPG (2) | DRS (3) | national | Dakar  | Régions |
|----------|----------|----------|---------|----------|--------|---------|
| 08/2026  | 9 000    | 4 000    | 3 000   | 16 000   | 13 000 | 3 000   |
| 09/2026  | 8 000    | 4 000    | 5 000   | 17 000   | 12 000 | 5 000   |
| 10/2026  | 10 000   | 6 000    | 4 000   | 20 000   | 16 000 | 4 000   |

NombreClient d'une interruption = Σ ``poste_interruptions.nombre_clients_estime`` (repli :
``nombre_clients_touches`` du poste) ; ``interruptions.nombre_clients_touches`` vaut 7 partout
pour détecter une lecture de la mauvaise colonne.

Période principale P = 15/09/2026 → 20/10/2026 :

| id  | statut   | apparition       | rég | svc | PS | F | nature | cause    | durée | clients (postes)  | compte ? |
|-----|----------|------------------|-----|-----|----|---|--------|----------|-------|-------------------|----------|
| 501 | valide   | 16/09/2026 08:00 | 1   | 1   | 1  | 1 | PERM   | 1        | 120   | 1000 (P1 600, P2 400) | oui incident hta |
| 502 | cloture  | 20/09/2026 10:00 | 1   | 2   | 2  | 3 | DEL    | 6 (PROD) | 60    | 2000 (P4)         | oui délestage htb |
| 503 | valide   | 25/09/2026 14:00 | 2   | 3   | 3  | 4 | COUP   | 3 (trav) | 240   | 300 (P5)          | oui travaux hta |
| 504 | archive  | 05/10/2026 09:00 | 1   | 1   | 1  | 2 | FUG    | 4 (exo)  | 30    | 100 (P3)          | oui incident hta |
| 505 | valide   | 12/10/2026 11:00 | 1   | 2   | 2  | 3 | PERM   | 2 (HTB)  | 90    | 800 (P4)          | oui autre htb |
| 506 | valide   | 18/10/2026 16:00 | 2   | 3   | 3  | 4 | FUG    | 1        | 15    | 200 (P5, estimé NULL, touchés 200) | oui incident hta |
| 507 | en_cours | 19/10/2026 08:00 | 1   | 1   | 1  | 1 | PERM   | 1        | —     | 600 (P1)          | non : en cours |
| 508 | valide   | 20/10/2026 22:00 | 1   | 4   | 1  | 1 | FUG    | 1        | 5     | 400 (P2)          | non : ≤ 5 min |
| 509 | brouillon (remise renseignée) | 10/10/2026 10:00 | 1 | 1 | 1 | 1 | PERM | 1 | 60 | 600 (P1) | non : statut |
| 510 | valide sans remise | 11/10/2026 10:00 | 1 | 1 | 1 | 1 | PERM | 1 | 60 | 600 (P1)   | non : remise |
| 511 | valide   | 13/10/2026 10:00 | 1   | —   | —  | — | PERM   | 1        | 60    | 50 (P6)           | non : sans service (hors périmètre) |
| 512 | transport valide | 14/10/2026 | 1 | 1   | 1  | 1 | PERM   | 1        | 100   | 9999 (P6)         | non : transport |
| 520 | valide   | 14/09/2026 23:00 | 1   | 1   | 1  | 1 | PERM   | 1        | 60    | 600 (P1)          | non : veille de P |
| 521 | valide   | 21/10/2026 00:00 | 1   | 1   | 1  | 1 | PERM   | 1        | 60    | 600 (P1)          | non : lendemain de P |

Autres périodes :
- B = 01/11 → 15/11/2026 : 530 valide 03/11/2026 10:00, Dakar, SDDV, PS 1, F 1, PERM, cause 1,
  60 min, 600 clients (P1). Novembre sans photo → base d'octobre.
- C = 01/08 → 10/09/2026 : 540 valide 10/08/2026 10:00, Dakar, SDDV, 60 min, 600 (P1) ;
  541 valide 05/09/2026 10:00, Dakar, SDDV, **5 min**, 400 (P2) : non comptée mais fixe le mois
  de la dernière apparition (septembre) ; 542 en cours 08/09/2026 (ignorée).
- J = 01/01 → 31/01/2026 : 550 valide 10/01/2026 10:00, SDDV, 60 min, 600 (P1) : aucune base.
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

PERIODE = {"debut": "2026-09-15", "fin": "2026-10-20"}
PERIODE_B = {"debut": "2026-11-01", "fin": "2026-11-15"}
PERIODE_C = {"debut": "2026-08-01", "fin": "2026-09-10"}
PERIODE_J = {"debut": "2026-01-01", "fin": "2026-01-31"}

# Base clients : (service, année, mois, clients)
BASE_CLIENTS: list[tuple[int, int, int, int]] = [
    (1, 2026, 8, 9000), (2, 2026, 8, 4000), (3, 2026, 8, 3000),
    (1, 2026, 9, 8000), (2, 2026, 9, 4000), (3, 2026, 9, 5000),
    (1, 2026, 10, 10000), (2, 2026, 10, 6000), (3, 2026, 10, 4000),
]

# (id, direction, statut, apparition, remise renseignée ?, région, service, PS, feeder, nature,
#  cause, durée minutes, postes [(poste, estimé, touchés)])
_INTERRUPTIONS: list[tuple[Any, ...]] = [
    (501, "distribution", "valide", "2026-09-16 08:00:00", True, 1, 1, 1, 1, 1, 1, 120, [(1, 600, 600), (2, 400, 400)]),
    (502, "distribution", "cloture", "2026-09-20 10:00:00", True, 1, 2, 2, 3, 3, 6, 60, [(4, 2000, 2000)]),
    (503, "distribution", "valide", "2026-09-25 14:00:00", True, 2, 3, 3, 4, 4, 3, 240, [(5, 300, 300)]),
    (504, "distribution", "archive", "2026-10-05 09:00:00", True, 1, 1, 1, 2, 2, 4, 30, [(3, 100, 100)]),
    (505, "distribution", "valide", "2026-10-12 11:00:00", True, 1, 2, 2, 3, 1, 2, 90, [(4, 800, 800)]),
    (506, "distribution", "valide", "2026-10-18 16:00:00", True, 2, 3, 3, 4, 2, 1, 15, [(5, None, 200)]),
    (507, "distribution", "en_cours", "2026-10-19 08:00:00", False, 1, 1, 1, 1, 1, 1, None, [(1, 600, 600)]),
    (508, "distribution", "valide", "2026-10-20 22:00:00", True, 1, 4, 1, 1, 2, 1, 5, [(2, 400, 400)]),
    (509, "distribution", "brouillon", "2026-10-10 10:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    (510, "distribution", "valide", "2026-10-11 10:00:00", False, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    (511, "distribution", "valide", "2026-10-13 10:00:00", True, 1, None, None, None, 1, 1, 60, [(6, 50, 50)]),
    (512, "transport", "valide", "2026-10-14 10:00:00", True, 1, 1, 1, 1, 1, 1, 100, [(6, 9999, 9999)]),
    (520, "distribution", "valide", "2026-09-14 23:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    (521, "distribution", "valide", "2026-10-21 00:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    # --- période B (novembre, sans photo) ---
    (530, "distribution", "valide", "2026-11-03 10:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    # --- période C (interruption brève en dernier) ---
    (540, "distribution", "valide", "2026-08-10 10:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
    (541, "distribution", "valide", "2026-09-05 10:00:00", True, 1, 1, 1, 1, 2, 1, 5, [(2, 400, 400)]),
    (542, "distribution", "en_cours", "2026-09-08 10:00:00", False, 1, 1, 1, 1, 1, 1, None, [(1, 600, 600)]),
    # --- période J (aucune base clients) ---
    (550, "distribution", "valide", "2026-01-10 10:00:00", True, 1, 1, 1, 1, 1, 1, 60, [(1, 600, 600)]),
]


def _modeles_saifi() -> list[Any]:
    from app.models.indicateurs import NombreClientMois

    return [*_modeles(), NombreClientMois]


def _v(x: Any) -> str:
    return "NULL" if x is None else repr(x)


def _inserts() -> list[str]:
    lignes = [
        "INSERT INTO regions (id, code, libelle, is_active) VALUES (1, 'DKR', 'DAKAR', 1), (2, 'REG', 'REGIONS', 1)",
        "INSERT INTO services (id, agence_id, region_id, code, libelle, is_active) VALUES "
        "(1, 1, 1, 'SDDV', 'Service Dakar Ville', 1), "
        "(2, 1, 1, 'SDPG', 'Service Pikine Guediawaye', 1), "
        "(3, 2, 2, 'DRS', 'Direction Regionale Sud', 1), "
        "(4, 1, 1, 'SDRBD', 'Service Rufisque Bargny Diamniadio', 1)",
        "INSERT INTO postes_sources (id, code, libelle, region_id, is_active) VALUES "
        "(1, 'PS-HANN', 'HANN', 1, 1), (2, 'PS-SOC', 'SOCOCIM', 1, 1), (3, 'PS-KAO', 'KAOLACK', 2, 1)",
        "INSERT INTO feeders (id, poste_source_id, service_id, region_id, code, libelle, is_active) VALUES "
        "(1, 1, 1, 1, 'F-HANN-1', 'HANN DEPART 1', 1), (2, 1, 1, 1, 'F-HANN-2', 'HANN DEPART 2', 1), "
        "(3, 2, 2, 1, 'F-BELAIR-2', 'BEL AIR 2', 1), (4, 3, 3, 2, 'F-KAO-V', 'KAOLACK VILLE', 1)",
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
        "INSERT INTO nombre_client_mois (id, service_id, annee, mois, nombre_clients) VALUES "
        + ", ".join(f"({i}, {s}, {a}, {m}, {n})" for i, (s, a, m, n) in enumerate(BASE_CLIENTS, start=1)),
    ]
    poste_id = 1
    for (
        iid, direction, statut, apparition, remise, region, service, ps, feeder, nature, cause, duree, postes,
    ) in _INTERRUPTIONS:
        date_remise = f"'{_d(apparition)}'" if remise else "NULL"
        lignes.append(
            "INSERT INTO interruptions (id, numero_interruption, type_direction, direction_source_id, statut, "
            "statut_id, region_id, service_id, poste_source_id, feeder_id, nature_id, cause_id, "
            "date_apparition, date_remise, duree_minutes, nombre_clients_touches, is_force_majeure, "
            "is_fugitive, created_by_id) VALUES "
            f"({iid}, {iid}, '{direction}', 1, '{statut}', 1, {_v(region)}, {_v(service)}, {_v(ps)}, "
            f"{_v(feeder)}, {_v(nature)}, {_v(cause)}, '{_d(apparition)}', {date_remise}, {_v(duree)}, 7, 0, 0, 1)"
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
                f"({poste_id}, {iid}, {poste}, {_v(feeder)}, {_v(service)}, {_v(ps)}, {_v(touches)}, {_v(estime)})"
            )
            poste_id += 1
    return lignes


@pytest_asyncio.fixture
async def session_saifi() -> AsyncIterator[AsyncSession]:
    """Base SQLite en mémoire remplie du jeu SAIFI / SAIDI ci-dessus."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"dbo": None}},
    )
    async with engine.begin() as connexion:
        for modele in _modeles_saifi():
            await connexion.exec_driver_sql(_ddl(modele))
        for ordre in _inserts():
            await connexion.exec_driver_sql(ordre)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client_saifi(session_saifi: AsyncSession, fake_redis: Any) -> AsyncIterator[AsyncClient]:
    """Client HTTP de l'application : base SQLite SAIFI, Redis fakeredis vidé."""
    from app.core.database import get_db
    from app.core.redis import get_redis
    from app.main import app

    await fake_redis.flushall()

    async def _db() -> AsyncIterator[AsyncSession]:
        yield session_saifi

    async def _redis() -> Any:
        return fake_redis

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_redis] = _redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
