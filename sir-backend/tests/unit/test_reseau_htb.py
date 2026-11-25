"""Réseau HTB d'une interruption distribution = sa cause (décision SENELEC du 25/11/2026).

HTB : le libellé de la cause contient « HTB », « PRODUCTION » ou « BLACK START » (casse et
accents ignorés), règle du rapport hebdomadaire DD. HTA : toutes les autres, y compris une
interruption sans cause. Ces tests sont écrits avant le code (circuit « tests avant le code »).
"""

import re
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.repositories.pilotage_repository import ClientsDureeRow
from app.services import saifi_saidi_service

PREFIXE = "app.services.saifi_saidi_service.pilotage_repository"
DEBUT = datetime(2026, 4, 1)
FIN = datetime(2026, 5, 1)


# --------------------------------------------------------------------------------------------
# 1. Règle pure : est_cause_htb
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        ("Défaut réseau HTB", True),
        ("déficit de production", True),
        ("black start poste", True),
        ("BLACK START", True),
        ("défaut htb", True),
        ("Défaut HTB", True),
        ("MANQUE PRODUCTION", True),
        ("Black-start", False),  # le texte doit contenir « BLACK START » avec une espace
        ("Câble HTA", False),
        ("INCONNUE", False),
        ("Manœuvre HTA", False),
        (None, False),
        ("", False),
        ("   ", False),
    ],
)
def test_est_cause_htb(libelle: str | None, attendu: bool) -> None:
    """Classement d'un libellé de cause en HTB (sinon HTA)."""
    from app.services.reseau_htb import est_cause_htb

    assert est_cause_htb(libelle) is attendu


def test_est_cause_htb_ignore_les_accents() -> None:
    """« PRODUCTÏON » (accent parasite) ou « htb » en minuscules accentuées restent HTB."""
    from app.services.reseau_htb import est_cause_htb

    assert est_cause_htb("Défaut de productión") is True
    assert est_cause_htb("Incident hTb Hann") is True


@pytest.mark.parametrize(
    "libelle",
    [
        "Défaut réseau HTB",
        "MANQUE PRODUCTION",
        "black start poste",
        "Black-start",
        "Câble HTA",
        "MANŒUVRE",
        "INCONNUE",
        None,
    ],
)
def test_categorie_hebdo_concorde_avec_est_cause_htb(libelle: str | None) -> None:
    """Le rapport hebdomadaire DD et la synthèse SAIFI/SAIDI appliquent la même règle HTB."""
    from app.repositories.rapport_hebdo_repository import LigneHebdo
    from app.services import rapport_hebdo_dd_service as hebdo
    from app.services.reseau_htb import est_cause_htb

    ligne = LigneHebdo(
        id=1, numero=1, statut="valide", date_apparition=datetime(2026, 10, 17, 8, 0),
        date_remise=datetime(2026, 10, 17, 9, 0), duree_minutes=60, service_id=1, service_code="SDDV",
        region_libelle="DAKAR", feeder="HANN 30KV", nature="PERMANENT", cause=libelle, end_mwh=0.5,
        clients=100, localisation="x",
    )
    est_htb_hebdo = hebdo.categorie(ligne) in (hebdo.HTB_DELESTAGE, hebdo.HTB_AUTRES)
    assert est_htb_hebdo is est_cause_htb(libelle)


# --------------------------------------------------------------------------------------------
# 2. Requête SQL : requete_sommes_clients (compilée pour SQL Server)
# --------------------------------------------------------------------------------------------


def _sql(reseau: str | None) -> str:
    from app.repositories import pilotage_repository as repo

    if reseau is None:
        requete = repo.requete_sommes_clients([1, 2], DEBUT, FIN)
    else:
        requete = repo.requete_sommes_clients([1, 2], DEBUT, FIN, reseau=reseau)
    return str(requete.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))


def _insensible_casse(sql: str) -> bool:
    return bool(re.search(r"(UPPER|LOWER)\s*\(", sql, re.IGNORECASE))


def test_requete_sommes_clients_sans_reseau_ne_filtre_pas_la_cause() -> None:
    """reseau=None : même requête qu'aujourd'hui (aucune jointure ni filtre sur causes)."""
    sql = _sql(None)
    assert "causes" not in sql.lower()
    assert "BIGINT" in sql.upper() and "FLOAT" in sql.upper()
    assert "IS 1" not in sql
    # conditions SAIFI/SAIDI conservées : distribution, règle des 5 minutes, bornes d'apparition
    assert "'distribution'" in sql
    assert "duree_minutes, 0) > 5" in sql
    assert "date_apparition >=" in sql and "date_apparition <" in sql
    assert "service_id IN (1, 2)" in sql


def test_requete_sommes_clients_htb_filtre_les_libelles() -> None:
    """reseau='htb' : jointure externe sur causes et LIKE sur HTB / PRODUCTION / BLACK START."""
    sql = _sql("htb")
    haut = sql.upper()
    assert "LEFT OUTER JOIN" in haut and "CAUSES" in haut
    for motif in ("'%HTB%'", "'%PRODUCTION%'", "'%BLACK START%'"):
        assert motif in haut, motif
    assert "LIKE" in haut
    assert _insensible_casse(sql)
    assert "BIGINT" in haut and "FLOAT" in haut
    assert "IS 1" not in sql
    assert "duree_minutes, 0) > 5" in sql


def test_requete_sommes_clients_hta_garde_les_interruptions_sans_cause() -> None:
    """reseau='hta' : négation du filtre HTB, interruptions sans cause (NULL) comprises."""
    sql = _sql("hta")
    haut = sql.upper()
    assert "LEFT OUTER JOIN" in haut and "CAUSES" in haut
    for motif in ("'%HTB%'", "'%PRODUCTION%'", "'%BLACK START%'"):
        assert motif in haut, motif
    assert "NOT" in haut
    # une cause NULL ne doit pas être éliminée par NOT (NULL LIKE …) : IS NULL ou COALESCE
    assert "IS NULL" in haut or re.search(r"COALESCE\([^)]*CAUSES\.LIBELLE", haut)
    assert _insensible_casse(sql)
    assert "BIGINT" in haut and "FLOAT" in haut
    assert "IS 1" not in sql


def test_requete_sommes_clients_reseaux_distincts() -> None:
    """Les trois variantes produisent trois requêtes différentes."""
    assert len({_sql(None), _sql("hta"), _sql("htb")}) == 3


# --------------------------------------------------------------------------------------------
# 3. Comportement réel de la requête (SQLite) : HTA + HTB = total
# --------------------------------------------------------------------------------------------


@pytest.fixture
async def db_sqlite():
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    async with engine.begin() as c:
        for ddl in (
            "CREATE TABLE causes (id INTEGER PRIMARY KEY, code TEXT, libelle TEXT, type_reseau TEXT, is_active INT)",
            "CREATE TABLE interruptions (id INTEGER PRIMARY KEY, service_id INT, region_id INT, "
            "type_direction TEXT, statut TEXT, date_apparition DATETIME, date_remise DATETIME, "
            "duree_minutes INT, cause_id INT)",
            "CREATE TABLE poste_interruptions (id INTEGER PRIMARY KEY, interruption_id INT, poste_id INT, "
            "nombre_clients_estime INT, nombre_clients_touches INT)",
            "INSERT INTO causes VALUES (1, 'C1', 'Défaut réseau HTB', 'distribution', 1), "
            "(2, 'C2', 'déficit de production', 'distribution', 1), "
            "(3, 'C3', 'Black start poste', 'distribution', 1), "
            "(4, 'C4', 'Câble HTA', 'distribution', 1), "
            "(5, 'C5', 'Black-start', 'distribution', 1)",
            # id, service, région, direction, statut, apparition, remise, durée (min), cause
            "INSERT INTO interruptions VALUES "
            "(10, 1, NULL, 'distribution', 'valide', '2026-04-02 08:00:00', '2026-04-02 09:00:00', 60, 1), "
            "(11, 1, NULL, 'distribution', 'cloture', '2026-04-03 08:00:00', '2026-04-03 10:00:00', 120, 2), "
            "(12, 2, NULL, 'distribution', 'valide', '2026-04-04 08:00:00', '2026-04-04 08:30:00', 30, 3), "
            "(13, 2, NULL, 'distribution', 'valide', '2026-04-05 08:00:00', '2026-04-05 09:00:00', 60, 4), "
            "(14, 1, NULL, 'distribution', 'archive', '2026-04-06 08:00:00', '2026-04-06 09:00:00', 60, NULL), "
            "(15, 1, NULL, 'distribution', 'valide', '2026-04-07 08:00:00', '2026-04-07 09:00:00', 60, 5), "
            # hors calcul : transport, en cours, 5 minutes, hors période, hors périmètre
            "(20, 1, NULL, 'transport', 'valide', '2026-04-02 08:00:00', '2026-04-02 09:00:00', 60, 1), "
            "(21, 1, NULL, 'distribution', 'en_cours', '2026-04-02 08:00:00', NULL, NULL, 1), "
            "(22, 1, NULL, 'distribution', 'valide', '2026-04-02 08:00:00', '2026-04-02 08:05:00', 5, 1), "
            "(23, 1, NULL, 'distribution', 'valide', '2026-05-02 08:00:00', '2026-05-02 09:00:00', 60, 1), "
            "(24, 9, NULL, 'distribution', 'valide', '2026-04-02 08:00:00', '2026-04-02 09:00:00', 60, 4)",
            "INSERT INTO poste_interruptions VALUES "
            "(1, 10, 1, 100, NULL), (2, 11, 1, 200, NULL), (3, 12, 1, NULL, 50), "
            "(4, 13, 1, 1000, NULL), (5, 14, 1, 400, NULL), (6, 15, 1, 70, NULL), "
            "(7, 20, 1, 9999, NULL), (8, 21, 1, 9999, NULL), (9, 22, 1, 9999, NULL), "
            "(10, 23, 1, 9999, NULL), (11, 24, 1, 9999, NULL)",
        ):
            await c.exec_driver_sql(ddl)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_sommer_clients_par_reseau_sur_donnees(db_sqlite: AsyncSession) -> None:
    """HTB = causes HTB / production / black start ; HTA = le reste et les sans-cause ; HTA + HTB = total."""
    from app.repositories import pilotage_repository as repo

    total = await repo.sommer_clients(db_sqlite, [1, 2], DEBUT, FIN)
    htb = await repo.sommer_clients(db_sqlite, [1, 2], DEBUT, FIN, reseau="htb")
    hta = await repo.sommer_clients(db_sqlite, [1, 2], DEBUT, FIN, reseau="hta")

    # HTB : 10 (100 × 1 h), 11 (200 × 2 h), 12 (50 touchés × 0,5 h)
    assert htb == ClientsDureeRow(clients=350, client_heures=525.0, nombre=3)
    # HTA : 13 (Câble HTA), 14 (sans cause), 15 (« Black-start » sans espace)
    assert hta == ClientsDureeRow(clients=1470, client_heures=1470.0, nombre=3)
    assert total == ClientsDureeRow(clients=1820, client_heures=1995.0, nombre=6)
    assert hta.clients + htb.clients == total.clients
    assert hta.nombre + htb.nombre == total.nombre
    assert abs(hta.client_heures + htb.client_heures - total.client_heures) < 1e-9


# --------------------------------------------------------------------------------------------
# 4. calculer_perimetre : numérateur par réseau, dénominateur commun
# --------------------------------------------------------------------------------------------


def _reseau_appel(appel) -> str | None:
    """Réseau passé à sommer_clients (mot-clé ou 5e argument positionnel)."""
    if "reseau" in appel.kwargs:
        return appel.kwargs["reseau"]
    return appel.args[4] if len(appel.args) > 4 else None


@pytest.mark.asyncio
@pytest.mark.parametrize("reseau", ["hta", "htb", None])
async def test_calculer_perimetre_transmet_le_reseau(reseau: str | None) -> None:
    """Le numérateur est filtré par réseau ; mois et base clients sont ceux de toute la distribution."""
    with (
        patch(f"{PREFIXE}.sommer_clients", AsyncMock(return_value=ClientsDureeRow(500, 550.0, 2))) as sommes,
        patch(f"{PREFIXE}.mois_derniere_apparition", AsyncMock(return_value=(2026, 4))) as mois,
        patch(f"{PREFIXE}.clients_reference_exacte", AsyncMock(return_value=10_000)) as ref,
    ):
        r = await saifi_saidi_service.calculer_perimetre(
            None, [1, 2], DEBUT, FIN, reseau=reseau  # type: ignore[arg-type]
        )
    sommes.assert_awaited_once()
    assert _reseau_appel(sommes.await_args) == reseau
    # dénominateur commun : aucun filtre réseau sur le mois ni sur la base clients
    mois.assert_awaited_once_with(None, [1, 2], DEBUT, FIN)
    ref.assert_awaited_once_with(None, [1, 2], 2026, 4)
    assert (r.saifi, r.saidi, r.nombre_interruptions, r.total_clients_reference) == (0.05, 0.055, 2, 10_000)


@pytest.mark.asyncio
async def test_calculer_perimetre_hta_plus_htb_egale_total() -> None:
    """Même base clients pour HTA, HTB et total : les SAIFI/SAIDI s'additionnent."""
    par_reseau = {
        "hta": ClientsDureeRow(3_000, 1_500.0, 7),
        "htb": ClientsDureeRow(1_000, 2_250.0, 2),
        None: ClientsDureeRow(4_000, 3_750.0, 9),
    }

    async def _sommes(*args: object, **kwargs: object) -> ClientsDureeRow:
        reseau = kwargs.get("reseau", args[4] if len(args) > 4 else None)
        return par_reseau[reseau]  # type: ignore[index]

    resultats = {}
    with (
        patch(f"{PREFIXE}.sommer_clients", AsyncMock(side_effect=_sommes)),
        # HTB n'a rien eu en avril : le mois reste celui de la distribution (avril, pas mars)
        patch(f"{PREFIXE}.mois_derniere_apparition", AsyncMock(return_value=(2026, 4))),
        patch(f"{PREFIXE}.clients_reference_exacte", AsyncMock(return_value=20_000)),
    ):
        for reseau in ("hta", "htb", None):
            resultats[reseau] = await saifi_saidi_service.calculer_perimetre(
                None, [1], DEBUT, FIN, reseau=reseau  # type: ignore[arg-type]
            )
    hta, htb, total = resultats["hta"], resultats["htb"], resultats[None]
    assert hta.total_clients_reference == htb.total_clients_reference == total.total_clients_reference == 20_000
    assert abs(total.saifi - (hta.saifi + htb.saifi)) < 1e-6
    assert abs(total.saidi - (hta.saidi + htb.saidi)) < 1e-6
    assert total.nombre_interruptions == hta.nombre_interruptions + htb.nombre_interruptions
