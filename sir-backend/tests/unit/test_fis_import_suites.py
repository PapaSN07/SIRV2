"""Import FIS — deuxième vague de correctifs (tests écrits avant le code).

Contrat :
- Signalisation lue dans le fichier et résolue dans le Référentiel (lecture seule) ;
- service, feeder et poste source trouvés par correspondance EXACTE (plus de LIKE), ambiguïté
  rejetée ; poste source de l'interruption = celui du feeder trouvé ;
- doublon = même numéro, distribution, même année (la numérotation repart à 1 chaque année) ;
  `skip_existing=False` rejette la ligne au lieu de créer un doublon ;
- `FisImportResult.creees` : (id, statut) des interruptions créées ;
- correspondances FIS administrées prioritaires sur la table interne et la recherche par libellé ;
- `_normalise` traite l'espace insécable ; un libellé rejeté n'est résolu qu'une fois par import ;
- `_find_system_user` (code mort) supprimé.
"""

from __future__ import annotations

import dataclasses
import io
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.models  # noqa: F401  (configuration des relations)
from app.models.geo import Agence, Region, Service
from app.models.interruptions import Interruption
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.reseau import Feeder, PosteSource
from app.services import fis_import_service as fis

M = "app.services.fis_import_service"


# ---------------------------------------------------------------------------
# Outils communs
# ---------------------------------------------------------------------------


def _moteur() -> Any:
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(
        moteur.sync_engine, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-26 08:00:00")
    )
    return moteur


def _row(numero: int = 1, **valeurs: Any) -> fis.FisRow:
    base: dict[str, Any] = {
        "numero": numero,
        "service_libelle": "SDDV",
        "source_libelle": "PS1",
        "tension_kv": 30.0,
        "feeder_libelle": "F1",
        "nature_libelle": "Permanent",
        "cause_libelle": "Agression",
        "siege_libelle": None,
        "date_apparition": datetime(2026, 6, 1, 8, 0),
        "date_remise": datetime(2026, 6, 1, 9, 0),
        "duree_minutes": 60,
        "puissance_kw": 1000.0,
        "end_kwh": 1000.0,
    }
    base.update(valeurs)
    return fis.FisRow(**base)


def _db_mock() -> MagicMock:
    """Session factice : les interruptions ajoutées reçoivent un id et sont gardées de côté."""
    db = MagicMock()
    db.flush = AsyncMock()
    savepoint = MagicMock(is_active=True, commit=AsyncMock(), rollback=AsyncMock())
    db.begin_nested = AsyncMock(return_value=savepoint)
    db.interruptions = []

    def _add(objet: Any) -> None:
        if isinstance(objet, fis.Interruption):
            objet.id = 1000 + len(db.interruptions)
            db.interruptions.append(objet)

    db.add = MagicMock(side_effect=_add)
    return db


NATURE_PERMANENT = SimpleNamespace(id=1, code="PERMANENT", is_active=True)
CAUSE_AGRESSION = SimpleNamespace(id=2, code="AGRESSION", is_active=True, type_reseau="distribution")


async def _importer(
    rows: list[fis.FisRow],
    *,
    db: MagicMock | None = None,
    can_validate: bool = False,
    exists: Any = None,
    feeder: Any = None,
    poste_source: Any = None,
    service: Any = None,
    cause: Any = None,
    autres: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[Any, MagicMock, dict[str, Any]]:
    """Lance import_fis_file avec un Référentiel factice (nature, cause, siège résolus)."""
    db = db or _db_mock()
    mocks: dict[str, Any] = {
        "_interruption_exists": exists if exists is not None else AsyncMock(return_value=False),
        "_find_service": AsyncMock(return_value=service),
        "_find_poste_source": AsyncMock(return_value=poste_source),
        "_find_feeder": AsyncMock(return_value=feeder),
        "_get_or_create_nature": AsyncMock(return_value=NATURE_PERMANENT),
        "_get_or_create_cause": cause if cause is not None else AsyncMock(return_value=(CAUSE_AGRESSION, False)),
        "_get_or_create_siege": AsyncMock(return_value=None),
    }
    mocks.update(autres or {})
    with (
        patch(f"{M}.parse_fis_sheet", return_value=rows),
        patch(f"{M}._can_validate", return_value=can_validate),
        patch.object(fis.distribution_rules, "_read_scope", return_value=None),
        patch.object(fis.distribution_rules, "_ensure_service_in_write_scope", new_callable=AsyncMock),
        patch.object(fis.distribution_rules.repo, "region_du_depart", new_callable=AsyncMock, return_value=None),
    ):
        patches = [patch(f"{M}.{nom}", new=valeur) for nom, valeur in mocks.items()]
        for p in patches:
            p.start()
        try:
            result = await fis.import_fis_file(db, b"xlsx", current_user=SimpleNamespace(id=7), **kwargs)  # type: ignore[arg-type]
        finally:
            for p in patches:
                p.stop()
    return result, db, mocks


# ---------------------------------------------------------------------------
# A1. Signalisation — FisRow et lecture du fichier
# ---------------------------------------------------------------------------


def test_fisrow_signalisation_facultative_et_en_dernier() -> None:
    row = _row()
    assert row.signalisation_libelle is None
    assert dataclasses.fields(fis.FisRow)[-1].name == "signalisation_libelle"


def _classeur(entetes: list[str], lignes: list[list[Any]]) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = fis.SHEET_NAME
    ws.append(["Fiche d'incidents et de suivi"])
    ws.append(entetes)
    for ligne in lignes:
        ws.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


ENTETES = [
    "N°",
    "Service Distribution",
    "Source",
    "Tension primaire",
    "Feeder",
    "Nature présumée",
    "Cause présumée",
    "Siege présumé",
    "Signalisation",
    "Date d'apparition",
    "Date de remise",
    "Durée interruption",
    "Puissance coupée",
    "END",
]


def _ligne(numero: int, signalisation: str | None) -> list[Any]:
    return [
        numero,
        "SDDV",
        "HANN",
        30,
        "F1",
        "Permanent",
        "Agression",
        "Câble",
        signalisation,
        datetime(2026, 6, 1, 8, 0),
        datetime(2026, 6, 1, 9, 0),
        "1 h 00 m 00",
        1000,
        1000,
    ]


def test_parse_lit_la_colonne_signalisation() -> None:
    contenu = _classeur(ENTETES, [_ligne(1, "  Défaut terre "), _ligne(2, None)])
    rows = fis.parse_fis_sheet(contenu)
    assert [r.numero for r in rows] == [1, 2]
    assert rows[0].signalisation_libelle == "Défaut terre"
    assert rows[1].signalisation_libelle is None


def test_parse_sans_colonne_signalisation() -> None:
    entetes = [e for e in ENTETES if e != "Signalisation"]
    ligne = _ligne(3, None)
    del ligne[ENTETES.index("Signalisation")]
    rows = fis.parse_fis_sheet(_classeur(entetes, [ligne]))
    assert len(rows) == 1
    assert rows[0].signalisation_libelle is None
    assert rows[0].cause_libelle == "Agression"


# ---------------------------------------------------------------------------
# Base SQLite : Référentiel signalisations, services, postes sources, feeders, interruptions
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> Any:
    moteur = _moteur()
    async with moteur.begin() as conn:
        for modele in (Region, Agence, Service, PosteSource, Feeder, Signalisation, Interruption):
            await conn.run_sync(modele.__table__.create)
    async with AsyncSession(moteur, expire_on_commit=False) as session:
        session.add_all(
            [
                # Signalisations
                Signalisation(id=1, code="DEF_TERRE", libelle="Défaut terre", type_reseau="distribution", is_active=True),
                Signalisation(id=2, code="MAX_I", libelle="Maximum d'intensité", type_reseau="commun", is_active=True),
                Signalisation(id=3, code="BUCHHOLZ", libelle="Buchholz", type_reseau="transport", is_active=True),
                Signalisation(id=4, code="ANCIENNE", libelle="Ancienne signalisation", type_reseau="distribution", is_active=False),
                # Services
                Service(id=1, agence_id=1, code="SDDV", libelle="Dakar Ville", is_active=True),
                Service(id=2, agence_id=1, code="SDPG", libelle="Pikine Guediawaye", is_active=True),
                Service(id=3, agence_id=1, code="SDRBD", libelle="DAKAR", is_active=True),
                Service(id=4, agence_id=1, code="SDRT1", libelle="Service Thies", is_active=True),
                Service(id=5, agence_id=1, code="SDRT2", libelle="Service Thies", is_active=True),
                # Postes sources
                PosteSource(id=1, code="HANN", libelle="HANN", is_active=True),
                PosteSource(id=2, code="CDB", libelle="CAP DES BICHES", is_active=True),
                PosteSource(id=3, code="OLD", libelle="Ancien poste", is_active=False),
                PosteSource(id=4, code="TOB1", libelle="TOBENE", is_active=True),
                PosteSource(id=5, code="TOB2", libelle="TOBENE", is_active=True),
                # Feeders
                Feeder(id=10, code="F1", libelle="F1", poste_source_id=1, service_id=1, is_active=True),
                Feeder(id=11, code="F10", libelle="F10", poste_source_id=1, service_id=1, is_active=True),
                Feeder(id=12, code="YEN", libelle="YENNE", poste_source_id=2, service_id=2, is_active=True),
                Feeder(id=13, code="OUAKAM_1", libelle="OUAKAM", poste_source_id=1, service_id=1, is_active=True),
                Feeder(id=14, code="OUAKAM_2", libelle="OUAKAM", poste_source_id=2, service_id=2, is_active=True),
                Feeder(id=15, code="MBAO_A", libelle="MBAO", poste_source_id=1, service_id=3, is_active=True),
                Feeder(id=16, code="MBAO_B", libelle="MBAO", poste_source_id=2, service_id=3, is_active=True),
                Feeder(id=17, code="KM_A", libelle="KEUR MASSAR", poste_source_id=1, service_id=2, is_active=True),
                Feeder(id=18, code="KM_B", libelle="KEUR MASSAR", poste_source_id=2, service_id=3, is_active=True),
                Feeder(id=19, code="VIEUX_1", libelle="VIEUX DEPART", poste_source_id=1, service_id=1, is_active=False),
                Feeder(id=20, code="VIEUX_2", libelle="VIEUX DEPART", poste_source_id=2, service_id=2, is_active=True),
                # Interruptions (doublons par année)
                Interruption(
                    id=100, numero_interruption=5, type_direction="distribution", statut="valide",
                    date_apparition=datetime(2025, 12, 31, 23, 0), created_by_id=1,
                ),
                Interruption(
                    id=101, numero_interruption=6, type_direction="distribution", statut="cloture",
                    date_apparition=datetime(2026, 3, 1, 10, 0), created_by_id=1,
                ),
                Interruption(
                    id=102, numero_interruption=7, type_direction="transport", statut="valide",
                    date_apparition=datetime(2026, 3, 1, 10, 0), created_by_id=1,
                ),
            ]
        )
        await session.commit()
        yield session
    await moteur.dispose()


# ---------------------------------------------------------------------------
# A1. _resoudre_signalisation (Référentiel lu, jamais écrit)
# ---------------------------------------------------------------------------


async def test_signalisation_vide_retourne_none(db: AsyncSession) -> None:
    assert await fis._resoudre_signalisation(db, "") is None
    assert await fis._resoudre_signalisation(db, None) is None  # type: ignore[arg-type]
    assert await fis._resoudre_signalisation(db, "   ") is None


@pytest.mark.parametrize(("libelle", "attendu"), [("  défaut TERRE ", 1), ("Maximum d'intensité", 2)])
async def test_signalisation_distribution_ou_commun_par_libelle_exact(db: AsyncSession, libelle: str, attendu: int) -> None:
    signalisation = await fis._resoudre_signalisation(db, libelle)
    assert signalisation is not None and signalisation.id == attendu


@pytest.mark.parametrize("libelle", ["Buchholz", "Ancienne signalisation", "Défaut", "Signal inconnu xyz"])
async def test_signalisation_transport_inactive_partielle_ou_inconnue_rejetee(db: AsyncSession, libelle: str) -> None:
    avant = (await db.execute(select(func.count()).select_from(Signalisation))).scalar_one()
    with pytest.raises(ValueError) as exc_info:
        await fis._resoudre_signalisation(db, libelle)
    await db.flush()
    apres = (await db.execute(select(func.count()).select_from(Signalisation))).scalar_one()
    assert apres == avant, "l'import a créé une signalisation"
    message = str(exc_info.value)
    assert "Signalisation" in message
    assert libelle.strip() in message
    assert "référentiel" in message.lower()


async def test_interruption_porte_la_signalisation() -> None:
    resoudre = AsyncMock(return_value=SimpleNamespace(id=42, code="DEF_TERRE"))
    result, db, _ = await _importer(
        [_row(1, signalisation_libelle="Défaut terre")], autres={"_resoudre_signalisation": resoudre}
    )
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert db.interruptions[0].signalisation_id == 42
    assert resoudre.await_args.args[1] == "Défaut terre"


async def test_signalisation_inconnue_rejette_la_ligne() -> None:
    resoudre = AsyncMock(side_effect=ValueError("Signalisation « Xyz » : aucune entrée active dans le référentiel"))
    result, db, _ = await _importer([_row(1, signalisation_libelle="Xyz")], autres={"_resoudre_signalisation": resoudre})
    assert result.stats.importees == 0
    assert result.stats.erreurs == 1
    assert result.stats.erreurs_detail[0].startswith("Ligne N°1")
    assert "Signalisation" in result.stats.erreurs_detail[0]
    assert db.interruptions == []


# ---------------------------------------------------------------------------
# A2. _find_service : correspondance exacte, ambiguïté rejetée
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("libelle", "attendu"), [("sddv", 1), ("SDPG", 2), ("  dakar ville ", 1), ("DAKAR", 3)])
async def test_service_trouve_par_code_ou_libelle_exact(db: AsyncSession, libelle: str, attendu: int) -> None:
    service = await fis._find_service(db, libelle)
    assert service is not None and service.id == attendu


@pytest.mark.parametrize("libelle", ["DAK", "VILLE", "Pikine", "SDD", "", "INCONNU"])
async def test_service_sans_correspondance_partielle(db: AsyncSession, libelle: str) -> None:
    assert await fis._find_service(db, libelle) is None


async def test_service_de_libelle_ambigu_rejete(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="ambigu"):
        await fis._find_service(db, " service thies ")


# ---------------------------------------------------------------------------
# A3. _find_feeder : actif, code ou libellé exact, ambiguïté rejetée
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("libelle", "service_id", "attendu"),
    [
        ("F1", 1, 10),  # pas F10
        ("f1", None, 10),
        (" yenne ", 1, 12),  # départ partagé : un seul candidat, d'un autre service
        ("yen", 1, 12),  # par le code
        ("OUAKAM", 1, 13),  # deux candidats : celui du service
        ("ouakam", 2, 14),
        ("VIEUX DEPART", 1, 20),  # le feeder inactif du service est ignoré
    ],
)
async def test_feeder_trouve_exactement(db: AsyncSession, libelle: str, service_id: int | None, attendu: int) -> None:
    feeder = await fis._find_feeder(db, libelle, service_id)
    assert feeder is not None and feeder.id == attendu


@pytest.mark.parametrize(("libelle", "service_id"), [("F", 1), ("F100", 1), ("OUAK", 1), ("", 1), ("INCONNU", None)])
async def test_feeder_sans_correspondance_partielle(db: AsyncSession, libelle: str, service_id: int | None) -> None:
    assert await fis._find_feeder(db, libelle, service_id) is None


@pytest.mark.parametrize(
    ("libelle", "service_id"),
    [
        ("OUAKAM", None),  # plusieurs candidats, aucun service pour départager
        ("MBAO", 3),  # plusieurs candidats dans le service
        ("KEUR MASSAR", 1),  # aucun dans le service, plusieurs ailleurs
    ],
)
async def test_feeder_ambigu_rejete(db: AsyncSession, libelle: str, service_id: int | None) -> None:
    with pytest.raises(ValueError, match="ambigu"):
        await fis._find_feeder(db, libelle, service_id)


# ---------------------------------------------------------------------------
# A4. Poste source : celui du feeder, sinon recherche exacte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("libelle", "attendu"), [("hann", 1), (" cap des biches ", 2), ("cdb", 2)])
async def test_poste_source_exact(db: AsyncSession, libelle: str, attendu: int) -> None:
    poste = await fis._find_poste_source(db, libelle)
    assert poste is not None and poste.id == attendu


@pytest.mark.parametrize("libelle", ["CAP", "HAN", "Ancien poste", "", "INCONNU"])
async def test_poste_source_partiel_inactif_ou_inconnu(db: AsyncSession, libelle: str) -> None:
    assert await fis._find_poste_source(db, libelle) is None


async def test_poste_source_ambigu_rejete(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="ambigu"):
        await fis._find_poste_source(db, "tobene")


async def test_poste_source_vient_du_feeder_trouve() -> None:
    feeder = SimpleNamespace(id=10, poste_source_id=1, service_id=1)
    result, db, mocks = await _importer(
        [_row(1, source_libelle="CAP DES BICHES")],
        feeder=feeder,
        poste_source=SimpleNamespace(id=2),
    )
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert db.interruptions[0].feeder_id == 10
    assert db.interruptions[0].poste_source_id == 1
    mocks["_find_poste_source"].assert_not_awaited()


async def test_poste_source_du_fichier_a_defaut_de_feeder() -> None:
    result, db, mocks = await _importer([_row(1, source_libelle="HANN")], feeder=None, poste_source=SimpleNamespace(id=2))
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert db.interruptions[0].poste_source_id == 2
    assert mocks["_find_poste_source"].await_args.args[1] == "HANN"


async def test_feeder_ambigu_rejette_la_ligne() -> None:
    result, db, _ = await _importer(
        [_row(1)], autres={"_find_feeder": AsyncMock(side_effect=ValueError("Feeder « F1 » ambigu : 2 départs"))}
    )
    assert result.stats.importees == 0
    assert result.stats.erreurs == 1
    assert "ambigu" in result.stats.erreurs_detail[0]
    assert db.interruptions == []


# ---------------------------------------------------------------------------
# A5. Doublons : même numéro, distribution, même année
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("numero", "annee", "attendu"),
    [
        (5, 2025, True),
        (5, 2026, False),  # la numérotation repart à 1 chaque année
        (6, 2026, True),
        (6, 2025, False),
        (7, 2026, False),  # n° 7 transport : pas un doublon distribution
    ],
)
async def test_doublon_par_numero_et_annee(db: AsyncSession, numero: int, annee: int, attendu: bool) -> None:
    assert await fis._interruption_exists(db, numero, annee) is attendu


def _exists_par_annee(existants: set[tuple[int, int]]) -> AsyncMock:
    async def _exists(_db: Any, numero: int, annee: int) -> bool:
        return (numero, annee) in existants

    return AsyncMock(side_effect=_exists)


async def test_import_cherche_le_doublon_dans_l_annee_de_la_ligne() -> None:
    exists = _exists_par_annee({(5, 2025)})
    rows = [_row(5, date_apparition=datetime(2026, 2, 3, 8, 0))]
    result, db, _ = await _importer(rows, exists=exists)
    assert result.stats.doublons_ignores == 0
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert exists.await_args.args[1:] == (5, 2026) or (
        exists.await_args.kwargs.get("numero"),
        exists.await_args.kwargs.get("annee"),
    ) == (5, 2026)


async def test_doublon_ignore_avec_skip_existing() -> None:
    exists = _exists_par_annee({(5, 2026)})
    result, db, _ = await _importer([_row(5), _row(8)], exists=exists, skip_existing=True)
    assert result.stats.doublons_ignores == 1
    assert result.stats.importees == 1
    assert result.stats.erreurs == 0
    assert [i.numero_interruption for i in db.interruptions] == [8]


async def test_doublon_rejete_sans_skip_existing() -> None:
    exists = _exists_par_annee({(5, 2026)})
    result, db, _ = await _importer([_row(5), _row(8)], exists=exists, skip_existing=False)
    assert result.stats.importees == 1
    assert result.stats.doublons_ignores == 0
    assert result.stats.erreurs == 1
    motif = result.stats.erreurs_detail[0]
    assert motif.startswith("Ligne N°5")
    assert "déjà" in motif
    assert [i.numero_interruption for i in db.interruptions] == [8], "un doublon a été créé"


# ---------------------------------------------------------------------------
# A6. Résultat : interruptions créées
# ---------------------------------------------------------------------------


def test_resultat_creees_vide_par_defaut() -> None:
    assert fis.FisImportResult(stats=fis.FisImportStats()).creees == []


@pytest.mark.parametrize(("can_validate", "statut"), [(False, "cloture"), (True, "valide")])
async def test_resultat_liste_les_interruptions_creees(can_validate: bool, statut: str) -> None:
    result, db, _ = await _importer(
        [_row(1), _row(2, cause_libelle="Inconnue xyz"), _row(3)],
        can_validate=can_validate,
        cause=AsyncMock(
            side_effect=lambda _db, lib: (CAUSE_AGRESSION, False)
            if lib == "Agression"
            else (_ for _ in ()).throw(ValueError("Cause inconnue du référentiel"))
        ),
    )
    assert result.stats.importees == 2
    ids = [i.id for i in db.interruptions]
    assert result.creees == [(ids[0], statut), (ids[1], statut)]


# ---------------------------------------------------------------------------
# A7. Correspondances FIS administrées
# ---------------------------------------------------------------------------


def _ref(id_: int, code: str, *, actif: bool = True, type_reseau: str | None = "distribution") -> SimpleNamespace:
    return SimpleNamespace(id=id_, code=code, libelle=code.title(), is_active=actif, type_reseau=type_reseau)


def _corresp(categorie: str, cible: Any, *, is_force_majeure: bool | None = None) -> SimpleNamespace:
    valeurs = {"nature": None, "cause": None, "siege": None, "signalisation": None}
    valeurs[categorie] = cible
    return SimpleNamespace(
        id=1,
        categorie=categorie,
        nature_id=getattr(valeurs["nature"], "id", None),
        cause_id=getattr(valeurs["cause"], "id", None),
        siege_id=getattr(valeurs["siege"], "id", None),
        signalisation_id=getattr(valeurs["signalisation"], "id", None),
        is_force_majeure=is_force_majeure,
        **valeurs,
    )


@pytest.fixture
async def db_ref() -> Any:
    """Référentiel réel (SQLite) : les correspondances doivent passer avant la recherche par libellé."""
    moteur = _moteur()
    async with moteur.begin() as conn:
        for modele in (Nature, Cause, Siege, Signalisation):
            await conn.run_sync(modele.__table__.create)
    async with AsyncSession(moteur, expire_on_commit=False) as session:
        session.add_all(
            [
                Nature(id=1, code="PERMANENT", libelle="Permanent", is_active=True),
                Cause(id=1, code="AGRESSION", libelle="Agression", type_reseau="distribution", is_active=True),
                Siege(id=1, code="CABLE", libelle="Câble", type_reseau="distribution", is_active=True),
                Signalisation(id=1, code="DEF_TERRE", libelle="Défaut terre", type_reseau="distribution", is_active=True),
            ]
        )
        await session.commit()
        yield session
    await moteur.dispose()


class _SessionEnveloppee:
    """Session réelle (Référentiel SQLite) dont les interruptions sont interceptées."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.interruptions: list[Any] = []
        self.details: list[Any] = []
        savepoint = MagicMock(is_active=True, commit=AsyncMock(), rollback=AsyncMock())
        self.begin_nested = AsyncMock(return_value=savepoint)

    def add(self, objet: Any) -> None:
        if isinstance(objet, fis.Interruption):
            objet.id = 1000 + len(self.interruptions)
            self.interruptions.append(objet)
        elif isinstance(objet, fis.InterruptionDistribution):
            self.details.append(objet)
        else:
            self._session.add(objet)

    def __getattr__(self, nom: str) -> Any:
        return getattr(self._session, nom)


async def _importer_ref(db_ref: AsyncSession, rows: list[fis.FisRow], correspondances: Any) -> tuple[Any, _SessionEnveloppee]:
    session = _SessionEnveloppee(db_ref)
    with (
        patch(f"{M}.parse_fis_sheet", return_value=rows),
        patch(f"{M}._interruption_exists", new_callable=AsyncMock, return_value=False),
        patch(f"{M}._find_service", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._find_poste_source", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._find_feeder", new_callable=AsyncMock, return_value=None),
        patch(f"{M}._can_validate", return_value=False),
        patch.object(fis.distribution_rules, "_read_scope", return_value=None),
        patch.object(fis.distribution_rules.repo, "region_du_depart", new_callable=AsyncMock, return_value=None),
    ):
        result = await fis.import_fis_file(
            session, b"xlsx", current_user=SimpleNamespace(id=7), correspondances=correspondances  # type: ignore[arg-type]
        )
    return result, session


async def test_sans_correspondance_comportement_inchange(db_ref: AsyncSession) -> None:
    for correspondances in (None, {}):
        result, session = await _importer_ref(db_ref, [_row(1, siege_libelle="Câble")], correspondances)
        assert result.stats.importees == 1, result.stats.erreurs_detail
        interruption = session.interruptions[0]
        assert (interruption.nature_id, interruption.cause_id, interruption.siege_id) == (1, 1, 1)
        assert interruption.is_force_majeure is True  # « Agression » : force majeure de la table interne


async def test_correspondance_nature_prioritaire(db_ref: AsyncSession) -> None:
    cible = _ref(9, "COUPURE", type_reseau=None)
    corr = {("nature", "coupure pour travaux"): _corresp("nature", cible)}
    result, session = await _importer_ref(db_ref, [_row(1, nature_libelle="  Coupure pour TRAVAUX ")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].nature_id == 9
    assert session.details[0].is_programme is True  # drapeaux tirés de la nature cible


async def test_correspondance_nature_passe_avant_la_table_interne(db_ref: AsyncSession) -> None:
    # « Permanent » existe en base, mais la correspondance administrée l'emporte
    corr = {("nature", "permanent"): _corresp("nature", _ref(9, "SEMI_PERM", type_reseau=None))}
    result, session = await _importer_ref(db_ref, [_row(1, nature_libelle="Permanent")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].nature_id == 9


async def test_correspondance_cause_et_force_majeure(db_ref: AsyncSession) -> None:
    corr = {("cause", "chute de météorite"): _corresp("cause", _ref(8, "FACT_EXO"), is_force_majeure=True)}
    result, session = await _importer_ref(db_ref, [_row(1, cause_libelle="Chute de Météorite ")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].cause_id == 8
    assert session.interruptions[0].is_force_majeure is True


async def test_correspondance_cause_force_majeure_explicite_l_emporte(db_ref: AsyncSession) -> None:
    # « Agression » est force majeure dans la table interne ; la correspondance dit non
    corr = {("cause", "agression"): _corresp("cause", _ref(8, "DAGRESSION", type_reseau="commun"), is_force_majeure=False)}
    result, session = await _importer_ref(db_ref, [_row(1, cause_libelle="Agression")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].cause_id == 8
    assert session.interruptions[0].is_force_majeure is False


@pytest.mark.parametrize(("libelle", "attendu"), [("Agression", True), ("Chute de météorite", False)])
async def test_correspondance_cause_sans_force_majeure_suit_la_regle_actuelle(
    db_ref: AsyncSession, libelle: str, attendu: bool
) -> None:
    corr = {("cause", libelle.lower()): _corresp("cause", _ref(8, "DAGRESSION"), is_force_majeure=None)}
    result, session = await _importer_ref(db_ref, [_row(1, cause_libelle=libelle)], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].cause_id == 8
    assert session.interruptions[0].is_force_majeure is attendu


async def test_correspondance_siege(db_ref: AsyncSession) -> None:
    corr = {("siege", "boîte de jonction"): _corresp("siege", _ref(6, "JONCTION", type_reseau="commun"))}
    result, session = await _importer_ref(db_ref, [_row(1, siege_libelle="Boîte de jonction")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].siege_id == 6


async def test_correspondance_signalisation(db_ref: AsyncSession) -> None:
    corr = {("signalisation", "homopolaire"): _corresp("signalisation", _ref(5, "DEF_HOMOPOL"))}
    result, session = await _importer_ref(db_ref, [_row(1, signalisation_libelle=" Homopolaire")], corr)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].signalisation_id == 5


@pytest.mark.parametrize(
    ("categorie", "champ", "cible"),
    [
        ("nature", "nature_libelle", _ref(9, "COUPURE", actif=False, type_reseau=None)),
        ("cause", "cause_libelle", _ref(8, "TRAV_HTB", type_reseau="transport")),
        ("cause", "cause_libelle", _ref(8, "ANCIENNE", actif=False)),
        ("siege", "siege_libelle", _ref(6, "LIGNE", actif=False)),
        ("siege", "siege_libelle", _ref(6, "DISJ", type_reseau="transport")),
        ("signalisation", "signalisation_libelle", _ref(5, "BUCHHOLZ", type_reseau="transport")),
    ],
)
async def test_correspondance_vers_cible_invalide_rejette_la_ligne(
    db_ref: AsyncSession, categorie: str, champ: str, cible: Any
) -> None:
    corr = {(categorie, "libellé fis"): _corresp(categorie, cible)}
    result, session = await _importer_ref(db_ref, [_row(1, **{champ: "Libellé FIS"})], corr)
    assert result.stats.importees == 0
    assert result.stats.erreurs == 1
    assert result.stats.erreurs_detail[0].startswith("Ligne N°1")
    assert "correspondance" in result.stats.erreurs_detail[0].lower()
    assert session.interruptions == []


# ---------------------------------------------------------------------------
# A8. Normalisation : espace insécable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [("\xa0Agression\xa0", "agression"), ("Travaux\xa0réseau HTA", "travaux réseau hta"), (None, "")],
)
def test_normalise_espace_insecable(brut: str | None, attendu: str) -> None:
    assert fis._normalise(brut) == attendu


async def test_cause_avec_espace_insecable_trouvee_par_la_table_interne(db_ref: AsyncSession) -> None:
    result, session = await _importer_ref(db_ref, [_row(1, cause_libelle="Agression\xa0")], None)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    db_ref.add(Cause(id=2, code="INC_HTA", libelle="Incident HTA", type_reseau="distribution", is_active=True))
    await db_ref.flush()
    result, session = await _importer_ref(db_ref, [_row(2, cause_libelle="Incident\xa0réseau HTA")], None)
    assert result.stats.importees == 1, result.stats.erreurs_detail
    assert session.interruptions[0].cause_id == 2


# ---------------------------------------------------------------------------
# A9. Cache des rejets : un libellé rejeté n'est résolu qu'une fois par import
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fonction", "champ", "valeur_ok"),
    [
        ("_get_or_create_nature", "nature_libelle", NATURE_PERMANENT),
        ("_get_or_create_cause", "cause_libelle", (CAUSE_AGRESSION, False)),
        ("_get_or_create_siege", "siege_libelle", None),
    ],
)
async def test_libelle_rejete_resolu_une_seule_fois(fonction: str, champ: str, valeur_ok: Any) -> None:
    resolution = AsyncMock(side_effect=ValueError("Libellé « Inconnu xyz » : aucune entrée active dans le référentiel"))
    rows = [_row(1, **{champ: "Inconnu xyz"}), _row(2, **{champ: " inconnu XYZ "})]
    result, db, _ = await _importer(rows, autres={fonction: resolution})
    assert resolution.await_count == 1
    assert result.stats.erreurs == 2
    assert result.stats.importees == 0
    motifs = [m.split(":", 1)[1] for m in result.stats.erreurs_detail]
    assert result.stats.erreurs_detail[0].startswith("Ligne N°1")
    assert result.stats.erreurs_detail[1].startswith("Ligne N°2")
    assert motifs[0] == motifs[1]
    assert db.interruptions == []


async def test_service_ambigu_resolu_une_seule_fois() -> None:
    find = AsyncMock(side_effect=ValueError("Service « Service Thies » ambigu"))
    result, _, _ = await _importer([_row(1, service_libelle="Service Thies"), _row(2, service_libelle="Service Thies")],
                                   autres={"_find_service": find})
    assert find.await_count == 1
    assert result.stats.erreurs == 2
    assert all("ambigu" in m for m in result.stats.erreurs_detail)


# ---------------------------------------------------------------------------
# A10. Code mort
# ---------------------------------------------------------------------------


def test_find_system_user_supprime() -> None:
    assert not hasattr(fis, "_find_system_user")


# ---------------------------------------------------------------------------
# Requêtes compilées SQL Server : pas de LIKE, pas de IS 1
# ---------------------------------------------------------------------------


def _db_capture() -> tuple[MagicMock, list[Any]]:
    requetes: list[Any] = []
    resultat = MagicMock()
    resultat.scalar_one_or_none.return_value = None
    resultat.scalar.return_value = None
    resultat.first.return_value = None
    resultat.all.return_value = []
    resultat.scalars.return_value.first.return_value = None
    resultat.scalars.return_value.all.return_value = []
    resultat.scalars.return_value.__iter__ = lambda self: iter([])

    async def _execute(requete: Any, *args: Any, **kwargs: Any) -> Any:
        requetes.append(requete)
        return resultat

    async def _scalar(requete: Any, *args: Any, **kwargs: Any) -> Any:
        requetes.append(requete)
        return None

    async def _scalars(requete: Any, *args: Any, **kwargs: Any) -> Any:
        requetes.append(requete)
        return resultat.scalars.return_value

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    db.scalar = AsyncMock(side_effect=_scalar)
    db.scalars = AsyncMock(side_effect=_scalars)
    return db, requetes


@pytest.mark.parametrize(
    ("appel", "attendus"),
    [
        (lambda db: fis._find_service(db, "Dakar Ville"), ["services"]),
        (lambda db: fis._find_feeder(db, "F1", 1), ["feeders", "is_active = 1"]),
        (lambda db: fis._find_poste_source(db, "HANN"), ["postes_sources", "is_active = 1"]),
        (lambda db: fis._resoudre_signalisation(db, "Défaut terre"), ["signalisations", "is_active = 1", "type_reseau IN"]),
        (lambda db: fis._interruption_exists(db, 5, 2026), ["interruptions", "type_direction", "numero_interruption"]),
    ],
)
async def test_requetes_compilees_sql_server(appel: Any, attendus: list[str]) -> None:
    db, requetes = _db_capture()
    try:
        await appel(db)
    except ValueError:
        pass
    assert requetes, "aucune requête émise"
    sqls = [str(r.compile(dialect=mssql.dialect())) for r in requetes]
    tout = "\n".join(sqls)
    assert "LIKE" not in tout.upper(), tout
    assert "IS 1" not in tout and "IS 0" not in tout, tout
    for attendu in attendus:
        assert attendu.lower() in tout.lower(), f"{attendu!r} absent de {tout}"
