"""Import FIS : le Référentiel (natures, causes, sièges) est lu, jamais écrit.

Faille corrigée : `_get_or_create_nature` / `_get_or_create_cause` / `_get_or_create_siege`
créaient une entrée du Référentiel pour tout libellé inconnu (route ouverte au BCC, qui n'a
pas le droit d'écrire le Référentiel), retombaient en silence sur AUTRE / INCONNUE et
acceptaient une cause / un siège transport ou inactif, contrairement à la saisie manuelle
(`interruption_distribution_service._validate_referentiel_distribution`).

Contrat : entrée active (et, pour Cause / Siège, `type_reseau` distribution ou commun),
trouvée par le code des tables de correspondance puis par le libellé ; sinon `ValueError`
(catégorie + libellé + « référentiel ») et aucune ligne ajoutée aux tables du Référentiel.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.referentiel import Cause, Nature, Siege
from app.services import fis_import_service as fis

M = "app.services.fis_import_service"


# ---------------------------------------------------------------------------
# Base SQLite en mémoire : seules les tables du Référentiel utiles
# ---------------------------------------------------------------------------

NATURES = [
    Nature(code="PERMANENT", libelle="Permanent", is_active=True),
    Nature(code="FUGITIF", libelle="Fugitif", is_active=False),  # inactive
    Nature(code="MANQUE_TENSION", libelle="Manque de tension", is_active=True),  # hors correspondance
    Nature(code="ANCIENNE", libelle="Ancienne nature", is_active=False),  # hors correspondance, inactive
]

CAUSES = [
    Cause(code="AGRESSION", libelle="Agression", type_reseau="distribution", is_active=True),
    Cause(code="MANOEUVRE", libelle="Manoeuvre", type_reseau="commun", is_active=True),
    Cause(code="TRAV_HTB", libelle="Travaux réseau HTB", type_reseau="transport", is_active=True),
    Cause(code="INCENDIE", libelle="Incendie", type_reseau="distribution", is_active=False),
    Cause(code="CHUTE_ARBRE", libelle="Chute d'arbre", type_reseau="distribution", is_active=True),
    Cause(code="FOUDRE_HTB", libelle="Foudre poste HTB", type_reseau="transport", is_active=True),
]

SIEGES = [
    Siege(code="CABLE", libelle="Câble", type_reseau="distribution", is_active=True),
    Siege(code="CELLULE", libelle="Cellule", type_reseau="commun", is_active=True),
    Siege(code="DISJONCTEUR", libelle="Disjoncteur", type_reseau="transport", is_active=True),
    Siege(code="LIGNE", libelle="Ligne", type_reseau="distribution", is_active=False),
    Siege(code="ISOLATEUR", libelle="Isolateur", type_reseau="distribution", is_active=True),
]

# Codes de repli de l'ancien code : présents en base, ils ne doivent JAMAIS servir
# de destination silencieuse à un libellé inconnu.
REPLIS = [
    Nature(code="AUTRE", libelle="Autre", is_active=True),
    Cause(code="INCONNUE", libelle="Inconnue", type_reseau="distribution", is_active=True),
    Siege(code="AUTRE", libelle="Autre", type_reseau="distribution", is_active=True),
]


def _copie(objet: Any) -> Any:
    """Nouvelle instance ORM (une instance ne peut appartenir qu'à une session)."""
    colonnes = {c.key: getattr(objet, c.key) for c in objet.__table__.columns if c.key != "id"}
    return type(objet)(**colonnes)


async def _creer_base(*, avec_replis: bool) -> tuple[Any, AsyncSession]:
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    async with moteur.begin() as conn:
        for modele in (Nature, Cause, Siege):
            await conn.run_sync(modele.__table__.create)
    session = AsyncSession(moteur, expire_on_commit=False)
    lignes = NATURES + CAUSES + SIEGES + (REPLIS if avec_replis else [])
    session.add_all([_copie(o) for o in lignes])
    await session.commit()
    return moteur, session


@pytest.fixture
async def db():
    moteur, session = await _creer_base(avec_replis=False)
    yield session
    await session.close()
    await moteur.dispose()


@pytest.fixture
async def db_replis():
    moteur, session = await _creer_base(avec_replis=True)
    yield session
    await session.close()
    await moteur.dispose()


async def _compter(db: AsyncSession) -> tuple[int, int, int]:
    n = (await db.execute(select(func.count()).select_from(Nature))).scalar_one()
    c = (await db.execute(select(func.count()).select_from(Cause))).scalar_one()
    s = (await db.execute(select(func.count()).select_from(Siege))).scalar_one()
    return n, c, s


def _verifier_message(exc: BaseException, categories: tuple[str, ...], libelle: str) -> None:
    message = str(exc)
    assert any(cat in message for cat in categories), f"catégorie absente du message : {message!r}"
    assert libelle.strip() in message, f"libellé absent du message : {message!r}"
    assert "référentiel" in message.lower(), f"« référentiel » absent du message : {message!r}"


async def _rejet(db: AsyncSession, fonction: Any, libelle: str, categories: tuple[str, ...]) -> None:
    """La résolution lève ValueError et n'ajoute aucune ligne au Référentiel."""
    avant = await _compter(db)
    with pytest.raises(ValueError) as exc_info:
        await fonction(db, libelle)
    await db.flush()
    assert await _compter(db) == avant, "une entrée du Référentiel a été créée"
    _verifier_message(exc_info.value, categories, libelle)


NATURE_CAT = ("Nature",)
CAUSE_CAT = ("Cause",)
SIEGE_CAT = ("Siège", "Siege")


# ---------------------------------------------------------------------------
# Nature
# ---------------------------------------------------------------------------


async def test_nature_libelle_vide_retourne_none(db: AsyncSession) -> None:
    assert await fis._get_or_create_nature(db, "") is None
    assert await fis._get_or_create_nature(db, None) is None  # type: ignore[arg-type]


async def test_nature_correspondance_active_acceptee(db: AsyncSession) -> None:
    nature = await fis._get_or_create_nature(db, " PERMANENT ")
    assert nature is not None and nature.code == "PERMANENT"


async def test_nature_trouvee_par_libelle(db: AsyncSession) -> None:
    nature = await fis._get_or_create_nature(db, "  manque DE tension ")
    assert nature is not None and nature.code == "MANQUE_TENSION"


async def test_nature_libelle_inconnu_rejete(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_nature, "Nature farfelue xyz", NATURE_CAT)


async def test_nature_libelle_inconnu_sans_repli_sur_autre(db_replis: AsyncSession) -> None:
    await _rejet(db_replis, fis._get_or_create_nature, "Nature farfelue xyz", NATURE_CAT)


async def test_nature_code_mappe_absent_de_la_base(db: AsyncSession) -> None:
    # « Semi permanent » → SEMI_PERM, absent de la base
    await _rejet(db, fis._get_or_create_nature, "Semi permanent", NATURE_CAT)


async def test_nature_inactive_rejetee(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_nature, "Fugitif", NATURE_CAT)


async def test_nature_inactive_trouvee_par_libelle_rejetee(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_nature, "Ancienne nature", NATURE_CAT)


# ---------------------------------------------------------------------------
# Cause
# ---------------------------------------------------------------------------


async def test_cause_libelle_vide_retourne_none(db: AsyncSession) -> None:
    assert await fis._get_or_create_cause(db, "") == (None, False)
    assert await fis._get_or_create_cause(db, None) == (None, False)  # type: ignore[arg-type]


async def test_cause_distribution_acceptee_force_majeure_du_mapping(db: AsyncSession) -> None:
    cause, force_majeure = await fis._get_or_create_cause(db, "Agression")
    assert cause is not None and cause.code == "AGRESSION"
    assert force_majeure is True


async def test_cause_commun_acceptee(db: AsyncSession) -> None:
    cause, force_majeure = await fis._get_or_create_cause(db, "Manoeuvre")
    assert cause is not None and cause.code == "MANOEUVRE"
    assert force_majeure is False


async def test_cause_trouvee_par_libelle_sans_force_majeure(db: AsyncSession) -> None:
    cause, force_majeure = await fis._get_or_create_cause(db, "  CHUTE D'ARBRE ")
    assert cause is not None and cause.code == "CHUTE_ARBRE"
    assert force_majeure is False


async def test_cause_libelle_inconnu_rejete(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_cause, "Chute de météorite", CAUSE_CAT)


async def test_cause_libelle_inconnu_sans_repli_sur_inconnue(db_replis: AsyncSession) -> None:
    await _rejet(db_replis, fis._get_or_create_cause, "Chute de météorite", CAUSE_CAT)


async def test_cause_code_mappe_absent_de_la_base(db: AsyncSession) -> None:
    # « Facteurs exogènes » → FACT_EXO, absent de la base
    await _rejet(db, fis._get_or_create_cause, "Facteurs exogènes", CAUSE_CAT)


async def test_cause_inactive_rejetee(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_cause, "Incendie", CAUSE_CAT)


async def test_cause_transport_rejetee(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_cause, "Travaux réseau HTB", CAUSE_CAT)


async def test_cause_transport_trouvee_par_libelle_rejetee(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_cause, "Foudre poste HTB", CAUSE_CAT)


# ---------------------------------------------------------------------------
# Siège
# ---------------------------------------------------------------------------


async def test_siege_libelle_vide_retourne_none(db: AsyncSession) -> None:
    assert await fis._get_or_create_siege(db, "") is None
    assert await fis._get_or_create_siege(db, None) is None


async def test_siege_distribution_accepte(db: AsyncSession) -> None:
    siege = await fis._get_or_create_siege(db, "Câble")
    assert siege is not None and siege.code == "CABLE"


async def test_siege_commun_accepte(db: AsyncSession) -> None:
    siege = await fis._get_or_create_siege(db, "Cellule")
    assert siege is not None and siege.code == "CELLULE"


async def test_siege_trouve_par_libelle(db: AsyncSession) -> None:
    siege = await fis._get_or_create_siege(db, " ISOLATEUR ")
    assert siege is not None and siege.code == "ISOLATEUR"


async def test_siege_libelle_inconnu_rejete(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_siege, "Pylône béton", SIEGE_CAT)


async def test_siege_libelle_inconnu_sans_repli_sur_autre(db_replis: AsyncSession) -> None:
    await _rejet(db_replis, fis._get_or_create_siege, "Pylône béton", SIEGE_CAT)


async def test_siege_code_mappe_absent_de_la_base(db: AsyncSession) -> None:
    # « Transformateur » → TRANSFO, absent de la base
    await _rejet(db, fis._get_or_create_siege, "Transformateur", SIEGE_CAT)


async def test_siege_inactif_rejete(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_siege, "Ligne", SIEGE_CAT)


async def test_siege_transport_rejete(db: AsyncSession) -> None:
    await _rejet(db, fis._get_or_create_siege, "Disjoncteur", SIEGE_CAT)


# ---------------------------------------------------------------------------
# Bout en bout : import_fis_file sur la vraie base SQLite du Référentiel
# ---------------------------------------------------------------------------


class _SessionEnveloppee:
    """Session réelle (Référentiel en SQLite) dont les interruptions sont interceptées.

    Les tables `interruptions` / `interruptions_distribution` ne sont pas créées : les objets
    Interruption / InterruptionDistribution sont gardés de côté au lieu d'être écrits.
    Tout le reste (requêtes, ajouts au Référentiel, flush) va à la vraie session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.interruptions: list[fis.Interruption] = []
        self.details: list[fis.InterruptionDistribution] = []
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


def _row(numero: int, cause: str) -> fis.FisRow:
    return fis.FisRow(
        numero=numero,
        service_libelle="SDDV",
        source_libelle="PS1",
        tension_kv=30.0,
        feeder_libelle="F1",
        nature_libelle="Permanent",
        cause_libelle=cause,
        siege_libelle=None,
        date_apparition=datetime(2026, 6, 1, 8, 0),
        date_remise=datetime(2026, 6, 1, 9, 0),
        duree_minutes=60,
        puissance_kw=1000.0,
        end_kwh=1000.0,
    )


async def test_import_ligne_avec_cause_inconnue_rejetee_sans_creer_de_cause(db: AsyncSession) -> None:
    session = _SessionEnveloppee(db)
    rows = [_row(501, "Agression"), _row(502, "Chute de météorite")]
    causes_avant = (await db.execute(select(func.count()).select_from(Cause))).scalar_one()

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
        result = await fis.import_fis_file(session, b"xlsx", current_user=SimpleNamespace(id=7))  # type: ignore[arg-type]

    assert result.stats.total_lignes == 2
    assert result.stats.importees == 1
    assert result.stats.erreurs == 1
    assert [i.numero_interruption for i in session.interruptions] == [501]
    assert session.interruptions[0].is_force_majeure is True

    assert len(result.stats.erreurs_detail) == 1
    motif = result.stats.erreurs_detail[0]
    assert motif.startswith("Ligne N°502")
    assert "Cause" in motif
    assert "Chute de météorite" in motif
    assert "référentiel" in motif.lower()

    await db.flush()
    causes_apres = (await db.execute(select(func.count()).select_from(Cause))).scalar_one()
    assert causes_apres == causes_avant, "l'import a créé une Cause dans le Référentiel"
    cree = (await db.execute(select(Cause.id).where(Cause.libelle == "Chute de météorite"))).scalar_one_or_none()
    assert cree is None
