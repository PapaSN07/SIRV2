"""Service import FIS (Fiche d'Incidents et de Suivi) — BCC et BRC.

Lit le fichier Excel FIS (format SENELEC), extrait la feuille
«Détails interruptions» et crée les interruptions distribution avec l'END
déjà calculé (valeur issue du fichier FIS).

Règles d'accès (identiques à la saisie manuelle) :
- chaque ligne doit appartenir au périmètre d'écriture de l'utilisateur
  (BCC/BRC → sa région, Superviseur → son service) ; sinon elle est rejetée ;
- statut « valide » seulement si l'utilisateur a le droit de valider,
  sinon « cloture » : les interruptions passent par la file de validation ;
- le Référentiel (natures, causes, sièges, signalisations) est lu, jamais écrit :
  une valeur inconnue, inactive ou transport rejette la ligne avec un motif ;
- les correspondances FIS administrées (Admin SCR) passent avant la table interne ;
- service, feeder et poste source sont trouvés par correspondance exacte (code ou
  libellé), jamais par ressemblance ; une ambiguïté rejette la ligne ;
- doublon = même numéro, distribution, même année : ignoré (`skip_existing`) ou
  rejeté, jamais créé.

Formule END vérifiée sur données réelles :
    END (kWh) = Puissance_coupée (kW) × Durée (minutes) / 60

Correspondance FIS → SIRV2 :
    END_mwh = END_kwh / 1000
    puissance_mw = puissance_kw / 1000
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Service
from app.models.interruptions import Interruption, InterruptionDistribution
from app.models.interruption_statut_historique import ACTION_CREATION, ACTION_VALIDATION
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.reseau import Feeder, PosteSource
from app.models.utilisateurs import Utilisateur
from app.repositories import correspondance_fis_repository, interruption_statut_repository
from app.schemas.correspondance_fis import normaliser_libelle_fis
from app.services import interruption_distribution_service as distribution_rules

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de mapping FIS → codes référentiel SIRV2
# ---------------------------------------------------------------------------

# Nature présumée FIS libelle → code SIRV2
NATURE_LIBELLE_TO_CODE: dict[str, str] = {
    "permanent": "PERMANENT",
    "semi permanent": "SEMI_PERM",
    "fugitif": "FUGITIF",
    "délestage": "DELESTAGE",
    "coupure": "COUPURE",
}

# Cause présumée FIS libelle → (code SIRV2, is_force_majeure)
CAUSE_LIBELLE_TO_CODE: dict[str, tuple[str, bool]] = {
    "inconnue": ("INCONNUE", False),
    "agression": ("AGRESSION", True),
    "incident réseau hta": ("INC_HTA", False),
    "défaillance protections dt": ("DEF_PROT", False),
    "défaillance matériel dt": ("DEF_MAT_DT", False),
    "défaillance matériel htb": ("DEF_MAT_HTB", False),
    "travaux réseau hta": ("TRAV_HTA", False),
    "travaux réseau htb": ("TRAV_HTB", False),
    "travaux réseau bt": ("TRAV_BT", False),
    "facteurs exogènes": ("FACT_EXO", True),
    "incendie": ("INCENDIE", True),
    "non recherché": ("NON_RECHERCHE", False),
    "manoeuvre": ("MANOEUVRE", False),
    "essai sur défaut": ("ESSAI_DEF", False),
    "défaillance protection htb": ("DEF_PROT_HTB", False),
    "manque production": ("MANQUE_PROD", False),
}

# Siège présumé FIS libelle → code SIRV2
SIEGE_LIBELLE_TO_CODE: dict[str, str] = {
    "câble": "CABLE",
    "extrémité": "EXTREMITE",
    "ligature": "LIGATURE",
    "ligne": "LIGNE",
    "cellule": "CELLULE",
    "disjoncteur": "DISJONCTEUR",
    "transformateur": "TRANSFO",
    "autre élément hta": "AUTRE_HTA",
    "autre": "AUTRE",
}

# Natures qui correspondent à des coupures programmées (is_programme=True)
NATURES_PROGRAMMEES = {"COUPURE"}

# Natures fugitives
NATURES_FUGITIVES = {"FUGITIF"}

# Natures délestage (is_programme=False mais délestage)
NATURES_DELESTAGE = {"DELESTAGE"}

# Feuille contenant les données d'incidents
SHEET_NAME = "Détails interruptions"

# En-têtes attendus dans la feuille (insensible à la casse)
_COL_NUMERO = "n°"
_COL_SERVICE = "service distribution"
_COL_SOURCE = "source"
_COL_TENSION = "tension primaire"
_COL_FEEDER = "feeder"
_COL_NATURE = "nature présumée"
_COL_CAUSE = "cause présumée"
_COL_SIEGE = "siege présumé"
_COL_SIGNALISATION = "signalisation"
_COL_DATE_APPARITION = "date d'apparition"
_COL_DATE_REMISE = "date de remise"
_COL_DUREE = "durée interruption"
_COL_PUISSANCE = "puissance coupée"
_COL_END = "end"


# ---------------------------------------------------------------------------
# Structures de résultats
# ---------------------------------------------------------------------------


@dataclass
class FisRow:
    """Ligne parsée depuis la feuille 'Détails interruptions'."""

    numero: int
    service_libelle: str
    source_libelle: str
    tension_kv: float | None
    feeder_libelle: str
    nature_libelle: str
    cause_libelle: str
    siege_libelle: str | None
    date_apparition: datetime
    date_remise: datetime | None
    duree_minutes: int
    puissance_kw: float
    end_kwh: float
    troncon: str | None = None
    observations: str | None = None
    signalisation_libelle: str | None = None


@dataclass
class FisImportStats:
    total_lignes: int = 0
    importees: int = 0
    doublons_ignores: int = 0
    erreurs: int = 0
    end_total_kwh: float = 0.0
    erreurs_detail: list[str] = field(default_factory=list)


@dataclass
class FisImportResult:
    stats: FisImportStats
    periode_debut: datetime | None = None
    periode_fin: datetime | None = None
    services_touches: list[str] = field(default_factory=list)
    # (id, statut) des interruptions créées — historique des statuts (importer_fis)
    creees: list[tuple[int, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parsing Excel
# ---------------------------------------------------------------------------


def _region_du_compte(user) -> int | None:
    scope = distribution_rules._read_scope(user)
    return getattr(scope, "region_id", None) if scope is not None else None


def _normalise(s: str | None) -> str:
    """Normalise une chaîne : espace insécable remplacé, strip, minuscules."""
    return normaliser_libelle_fis(s)


def _find_header_row(ws) -> dict[str, int] | None:  # type: ignore[type-arg]
    """Détecte la ligne d'en-tête et retourne un dict col_name → col_index."""
    for row in ws.iter_rows(values_only=True):
        # La ligne d'en-tête contient "N°" ou "n°" dans la 1re cellule non-None
        cells = [c for c in row if c is not None]
        if not cells:
            continue
        first = _normalise(str(cells[0]))
        if first == _COL_NUMERO:
            return {_normalise(str(v)): i for i, v in enumerate(row) if v is not None}
    return None


def _col(headers: dict[str, int], name: str) -> int | None:
    """Retourne l'index de colonne pour le nom (recherche préfixe insensible casse)."""
    # Exact match
    if name in headers:
        return headers[name]
    # Prefix match (ex: "source" matche "source ")
    for key, idx in headers.items():
        if key.startswith(name):
            return idx
    return None


def _parse_duration(val: Any) -> int:
    """Convertit une valeur de durée en minutes entiers."""
    if val is None:
        return 0
    if isinstance(val, timedelta):
        return int(val.total_seconds() / 60)
    if isinstance(val, str):
        # Format "0 h 31 m 00" ou "1 h 22 m 00"
        import re

        m = re.match(r"(\d+)\s*h\s*(\d+)\s*m", val)
        if m:
            return int(m.group(1)) * 60 + int(m.group(2))
    return 0


def _parse_float(val: Any) -> float:
    """Convertit une valeur numérique en float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _parse_datetime(val: Any) -> datetime | None:
    """Retourne un datetime ou None."""
    if isinstance(val, datetime):
        return val
    return None


def _texte_facultatif(val: Any) -> str | None:
    """Texte nettoyé (espaces de bord, espace insécable compris) ou None si vide."""
    if val is None:
        return None
    texte = str(val).replace("\xa0", " ").strip()
    return texte or None


def parse_fis_sheet(file_bytes: bytes) -> list[FisRow]:
    """Lit un fichier FIS Excel et retourne les lignes de 'Détails interruptions'."""
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl requis : pip install openpyxl") from exc

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)

    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Feuille '{SHEET_NAME}' introuvable. " f"Feuilles disponibles : {wb.sheetnames}")

    ws = wb[SHEET_NAME]
    headers = _find_header_row(ws)
    if headers is None:
        raise ValueError(
            f"Ligne d'en-tête introuvable dans '{SHEET_NAME}' " "(colonnes attendues : N°, Service Distribution, …)"
        )

    # Index des colonnes clés
    idx_num = _col(headers, _COL_NUMERO)
    idx_svc = _col(headers, _COL_SERVICE)
    idx_src = _col(headers, _COL_SOURCE)
    idx_ten = _col(headers, _COL_TENSION)
    idx_fdr = _col(headers, _COL_FEEDER)
    idx_nat = _col(headers, _COL_NATURE)
    idx_cau = _col(headers, _COL_CAUSE)
    idx_sie = _col(headers, _COL_SIEGE)
    idx_da = _col(headers, _COL_DATE_APPARITION)
    idx_dr = _col(headers, _COL_DATE_REMISE)
    idx_dur = _col(headers, _COL_DUREE)
    idx_pui = _col(headers, _COL_PUISSANCE)
    idx_end = _col(headers, _COL_END)

    # Colonnes optionnelles
    idx_trc = _col(headers, "tronçon")
    idx_obs = _col(headers, "observation")
    idx_sig = _col(headers, _COL_SIGNALISATION)

    required_cols = {
        "N°": idx_num,
        "Service Distribution": idx_svc,
        "Feeder": idx_fdr,
        "Date d'apparition": idx_da,
        "Puissance coupée": idx_pui,
        "END": idx_end,
    }
    missing = [name for name, idx in required_cols.items() if idx is None]
    if missing:
        raise ValueError(f"Colonnes manquantes dans FIS : {missing}")

    rows: list[FisRow] = []
    header_passed = False

    for raw_row in ws.iter_rows(values_only=True):
        # Skip jusqu'après la ligne d'en-tête
        if not header_passed:
            cells = [c for c in raw_row if c is not None]
            if cells and _normalise(str(cells[0])) == _COL_NUMERO:
                header_passed = True
            continue

        # Ignorer les lignes vides ou sans numéro
        num_val = raw_row[idx_num] if idx_num is not None else None  # type: ignore[index]
        if num_val is None or not isinstance(num_val, int):
            continue

        svc_val = raw_row[idx_svc] if idx_svc is not None else None  # type: ignore[index]
        da_val = raw_row[idx_da] if idx_da is not None else None  # type: ignore[index]
        dr_val = raw_row[idx_dr] if idx_dr is not None else None  # type: ignore[index]
        dur_val = raw_row[idx_dur] if idx_dur is not None else None  # type: ignore[index]
        pui_val = raw_row[idx_pui] if idx_pui is not None else None  # type: ignore[index]
        end_val = raw_row[idx_end] if idx_end is not None else None  # type: ignore[index]

        da = _parse_datetime(da_val)
        if da is None:
            continue  # date_apparition obligatoire

        rows.append(
            FisRow(
                numero=int(num_val),
                service_libelle=str(svc_val).strip() if svc_val else "",
                source_libelle=str(raw_row[idx_src]).strip() if idx_src is not None and raw_row[idx_src] else "",  # type: ignore[index]
                tension_kv=_parse_float(raw_row[idx_ten]) if idx_ten is not None else None,  # type: ignore[index]
                feeder_libelle=str(raw_row[idx_fdr]).strip() if idx_fdr is not None and raw_row[idx_fdr] else "",  # type: ignore[index]
                nature_libelle=str(raw_row[idx_nat]).strip() if idx_nat is not None and raw_row[idx_nat] else "",  # type: ignore[index]
                cause_libelle=str(raw_row[idx_cau]).strip() if idx_cau is not None and raw_row[idx_cau] else "",  # type: ignore[index]
                siege_libelle=str(raw_row[idx_sie]).strip() if idx_sie is not None and raw_row[idx_sie] else None,  # type: ignore[index]
                date_apparition=da,
                date_remise=_parse_datetime(dr_val),
                duree_minutes=_parse_duration(dur_val),
                puissance_kw=_parse_float(pui_val),
                end_kwh=_parse_float(end_val),
                troncon=str(raw_row[idx_trc]).strip() if idx_trc is not None and raw_row[idx_trc] else None,  # type: ignore[index]
                observations=str(raw_row[idx_obs]).strip() if idx_obs is not None and raw_row[idx_obs] else None,  # type: ignore[index]
                signalisation_libelle=_texte_facultatif(raw_row[idx_sig]) if idx_sig is not None else None,  # type: ignore[index]
            )
        )

    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Résolution des référentiels DB — lecture seule
# ---------------------------------------------------------------------------
#
# L'import FIS est ouvert au BCC, qui n'a pas le droit d'écrire le Référentiel
# (`referentiel_service._ensure_can_write`) : il ne crée JAMAIS de nature, cause
# ou siège. Il ne rattache qu'une entrée active et, pour une cause ou un siège,
# de type distribution ou commun (mêmes règles que la saisie manuelle,
# `interruption_distribution_service._validate_referentiel_distribution`).
# Sinon la ligne est rejetée avec un motif, sans repli silencieux sur AUTRE /
# INCONNUE (classement faux dans les indicateurs).

_TYPES_RESEAU_DISTRIBUTION = tuple(sorted(distribution_rules._DISTRIBUTION_TYPE_RESEAU))


def _code_depuis_libelle(key: str, correspondances: dict[str, Any]) -> Any:
    """Correspondance EXACTE d'un libellé FIS normalisé (None sinon).

    Pas de correspondance partielle : « Défaut semi-permanent » deviendrait
    PERMANENT, « Autre élément BT » AUTRE. À défaut, l'entrée est cherchée par
    son libellé exact en base, puis la ligne est rejetée.
    """
    return correspondances.get(key)


async def _resoudre_referentiel(
    db: AsyncSession,
    modele: type[Nature] | type[Cause] | type[Siege],
    categorie: str,
    libelle: str,
    code: str | None,
    *,
    filtrer_type_reseau: bool,
) -> Any:
    """Entrée valide trouvée par code puis par libellé, sinon ValueError (rien n'est créé)."""
    conditions = [modele.is_active == true()]
    if filtrer_type_reseau:
        conditions.append(modele.type_reseau.in_(_TYPES_RESEAU_DISTRIBUTION))  # type: ignore[union-attr]

    if code is not None:
        result = await db.execute(select(modele).where(modele.code == code, *conditions))
        entree = result.scalar_one_or_none()
        if entree is not None:
            return entree

    key = _normalise(libelle)
    result = await db.execute(
        select(modele).where(func.lower(func.trim(modele.libelle)) == key, *conditions).order_by(modele.id).limit(1)
    )
    entree = result.scalars().first()
    if entree is not None:
        return entree

    precision = " de type distribution ou commun" if filtrer_type_reseau else ""
    raise ValueError(
        f"{categorie} « {libelle.strip()} » : aucune entrée active{precision} dans le référentiel "
        "(l'import n'en crée pas — l'Admin SCR peut l'associer à une entrée existante : "
        "Référentiel → Correspondances FIS)"
    )


async def _get_or_create_nature(db: AsyncSession, libelle: str) -> Nature | None:
    """Résout une Nature existante et active (nom historique : ne crée plus rien)."""
    if not libelle:
        return None
    code = _code_depuis_libelle(_normalise(libelle), NATURE_LIBELLE_TO_CODE)
    return await _resoudre_referentiel(db, Nature, "Nature", libelle, code, filtrer_type_reseau=False)


async def _get_or_create_cause(db: AsyncSession, libelle: str) -> tuple[Cause | None, bool]:
    """Résout une Cause existante, active, distribution ou commun. Retourne (cause, is_force_majeure).

    Nom historique : ne crée plus rien. Force majeure d'après la correspondance FIS
    du libellé, quelle que soit l'entrée trouvée ; False pour un libellé hors correspondance.
    """
    if not libelle:
        return None, False
    mapping = _code_depuis_libelle(_normalise(libelle), CAUSE_LIBELLE_TO_CODE)
    code, is_fm = mapping if mapping is not None else (None, False)
    cause = await _resoudre_referentiel(db, Cause, "Cause", libelle, code, filtrer_type_reseau=True)
    # La force majeure suit le libellé FIS (les codes migrés diffèrent : DAGRESSION…)
    return cause, is_fm


async def _get_or_create_siege(db: AsyncSession, libelle: str | None) -> Siege | None:
    """Résout un Siège existant, actif, distribution ou commun (nom historique : ne crée plus rien)."""
    if not libelle:
        return None
    code = _code_depuis_libelle(_normalise(libelle), SIEGE_LIBELLE_TO_CODE)
    return await _resoudre_referentiel(db, Siege, "Siège", libelle, code, filtrer_type_reseau=True)


async def _resoudre_signalisation(db: AsyncSession, libelle: str | None) -> Signalisation | None:
    """Résout une Signalisation existante, active, distribution ou commun (libellé exact).

    Comme les autres entrées du Référentiel : rien n'est créé, une valeur inconnue, inactive
    ou transport lève ValueError (la ligne est rejetée).
    """
    if not _normalise(libelle):
        return None
    return await _resoudre_referentiel(
        db, Signalisation, "Signalisation", libelle or "", None, filtrer_type_reseau=True
    )


# ---------------------------------------------------------------------------
# Correspondances FIS administrées (Admin SCR) — prioritaires
# ---------------------------------------------------------------------------

_NOMS_CATEGORIES: dict[str, str] = {
    "nature": "Nature",
    "cause": "Cause",
    "siege": "Siège",
    "signalisation": "Signalisation",
}


def _correspondance(correspondances: dict[tuple[str, str], Any] | None, categorie: str, libelle: str | None) -> Any:
    """Correspondance administrée du libellé (clé normalisée), None sinon."""
    if not correspondances:
        return None
    cle = _normalise(libelle)
    if not cle:
        return None
    return correspondances.get((categorie, cle))


def _cible_correspondance(correspondance: Any, categorie: str, libelle: str) -> Any:
    """Entrée visée par la correspondance, contrôlée comme une saisie manuelle (sinon ValueError)."""
    cible = getattr(correspondance, categorie, None)
    nom = _NOMS_CATEGORIES[categorie]
    if cible is None:
        raise ValueError(
            f"{nom} « {libelle.strip()} » : la correspondance FIS ne pointe vers aucune entrée du référentiel"
        )
    hors_distribution = categorie != "nature" and getattr(cible, "type_reseau", None) not in _TYPES_RESEAU_DISTRIBUTION
    if not cible.is_active or hors_distribution:
        raise ValueError(
            f"{nom} « {libelle.strip()} » : la correspondance FIS pointe vers « {cible.code} », "
            "inactive ou hors distribution dans le référentiel (à corriger par l'Admin SCR)"
        )
    return cible


async def _resoudre_nature(
    db: AsyncSession, libelle: str, correspondances: dict[tuple[str, str], Any] | None
) -> Nature | None:
    correspondance = _correspondance(correspondances, "nature", libelle)
    if correspondance is not None:
        return _cible_correspondance(correspondance, "nature", libelle)
    return await _get_or_create_nature(db, libelle)


async def _resoudre_cause(
    db: AsyncSession, libelle: str, correspondances: dict[tuple[str, str], Any] | None
) -> tuple[Cause | None, bool]:
    correspondance = _correspondance(correspondances, "cause", libelle)
    if correspondance is None:
        return await _get_or_create_cause(db, libelle)
    cause = _cible_correspondance(correspondance, "cause", libelle)
    if correspondance.is_force_majeure is not None:
        return cause, bool(correspondance.is_force_majeure)
    # Force majeure non précisée : règle de la table interne (False hors table)
    mapping = _code_depuis_libelle(_normalise(libelle), CAUSE_LIBELLE_TO_CODE)
    return cause, mapping[1] if mapping is not None else False


async def _resoudre_siege(
    db: AsyncSession, libelle: str | None, correspondances: dict[tuple[str, str], Any] | None
) -> Siege | None:
    correspondance = _correspondance(correspondances, "siege", libelle)
    if correspondance is not None:
        return _cible_correspondance(correspondance, "siege", libelle or "")
    return await _get_or_create_siege(db, libelle)


async def _resoudre_signalisation_fis(
    db: AsyncSession, libelle: str | None, correspondances: dict[tuple[str, str], Any] | None
) -> Signalisation | None:
    correspondance = _correspondance(correspondances, "signalisation", libelle)
    if correspondance is not None:
        return _cible_correspondance(correspondance, "signalisation", libelle or "")
    return await _resoudre_signalisation(db, libelle)


# ---------------------------------------------------------------------------
# Service, feeder, poste source — correspondance exacte (code ou libellé)
# ---------------------------------------------------------------------------
#
# Plus de recherche par ressemblance (`LIKE %…%`) : « DAK » trouvait « DAKAR »,
# « F1 » trouvait « F10 ». Plusieurs candidats → ValueError « ambigu » (ligne rejetée).

_MAX_CANDIDATS = 50


def _egal_normalise(colonne: Any, cle: str) -> Any:
    return func.lower(func.trim(colonne)) == cle


def _ambigu(categorie: str, libelle: str, nombre: int) -> ValueError:
    return ValueError(
        f"{categorie} « {libelle.strip()} » ambigu : {nombre} correspondances exactes, "
        "préciser le code dans le fichier"
    )


async def _find_service(db: AsyncSession, libelle: str) -> Service | None:
    """Service par code exact, sinon par libellé exact (insensible à la casse) ; ValueError si ambigu."""
    cle = _normalise(libelle)
    if not cle:
        return None
    for colonne in (Service.code, Service.libelle):
        result = await db.execute(
            select(Service)
            .where(Service.is_active == true(), _egal_normalise(colonne, cle))
            .order_by(Service.id)
            .limit(2)
        )
        candidats = list(result.scalars().all())
        if len(candidats) == 1:
            return candidats[0]
        if len(candidats) > 1:
            raise _ambigu("Service", libelle, len(candidats))
    return None


async def _postes_sources_nommes(db: AsyncSession, libelle: str | None) -> set[int]:
    """Identifiants des postes sources actifs dont le code ou le libellé égale le texte."""
    cle = _normalise(libelle)
    if not cle:
        return set()
    result = await db.execute(
        select(PosteSource.id).where(
            PosteSource.is_active == true(),
            or_(_egal_normalise(PosteSource.code, cle), _egal_normalise(PosteSource.libelle, cle)),
        )
    )
    return set(result.scalars().all())


async def _departager_par_source(
    db: AsyncSession, candidats: list[Feeder], source_libelle: str | None
) -> list[Feeder]:
    """Feeders homonymes (« DEPART 1 » sous plusieurs postes sources) : garde ceux de la Source du fichier."""
    if len(candidats) < 2 or not source_libelle:
        return candidats
    sources = await _postes_sources_nommes(db, source_libelle)
    retenus = [f for f in candidats if f.poste_source_id in sources]
    return retenus or candidats


async def _find_feeder(
    db: AsyncSession, libelle: str, service_id: int | None, source_libelle: str | None = None
) -> Feeder | None:
    """Feeder actif par code ou libellé exact.

    Plusieurs candidats : ceux du service de la ligne, puis ceux du poste source du fichier ;
    aucun dans le service : un candidat unique d'un autre service est accepté (départ partagé,
    ex. YEN) ; sinon ValueError « ambigu ».
    """
    cle = _normalise(libelle)
    if not cle:
        return None
    result = await db.execute(
        select(Feeder)
        .where(
            Feeder.is_active == true(),
            or_(_egal_normalise(Feeder.code, cle), _egal_normalise(Feeder.libelle, cle)),
        )
        .order_by(Feeder.id)
        .limit(_MAX_CANDIDATS)
    )
    candidats = list(result.scalars().all())
    if service_id is not None:
        du_service = await _departager_par_source(
            db, [f for f in candidats if f.service_id == service_id], source_libelle
        )
        if len(du_service) == 1:
            return du_service[0]
        if len(du_service) > 1:
            raise _ambigu("Feeder", libelle, len(du_service))
    candidats = await _departager_par_source(db, candidats, source_libelle)
    if len(candidats) == 1:
        return candidats[0]
    if len(candidats) > 1:
        raise _ambigu("Feeder", libelle, len(candidats))
    return None


async def _find_poste_source(db: AsyncSession, libelle: str) -> PosteSource | None:
    """Poste source actif par code ou libellé exact ; ValueError si ambigu."""
    cle = _normalise(libelle)
    if not cle:
        return None
    result = await db.execute(
        select(PosteSource)
        .where(
            PosteSource.is_active == true(),
            or_(_egal_normalise(PosteSource.code, cle), _egal_normalise(PosteSource.libelle, cle)),
        )
        .order_by(PosteSource.id)
        .limit(2)
    )
    candidats = list(result.scalars().all())
    if len(candidats) > 1:
        raise _ambigu("Poste source", libelle, len(candidats))
    return candidats[0] if candidats else None


async def _interruption_exists(db: AsyncSession, numero: int, annee: int) -> bool:
    """Interruption distribution de même numéro dans la même année (la numérotation repart à 1).

    Filtre par intervalle de dates (et non DATEPART) : l'index sur date_apparition reste utilisable.
    """
    debut = datetime(annee, 1, 1)
    fin = datetime(annee + 1, 1, 1)
    result = await db.execute(
        select(Interruption.id)
        .where(
            Interruption.numero_interruption == numero,
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .limit(1)
    )
    return result.scalars().first() is not None


async def _rollback_savepoint(savepoint: Any) -> None:
    if savepoint is not None and savepoint.is_active:
        await savepoint.rollback()


async def _en_cache(cache: dict[Any, Any], cle: Any, fabrique: Callable[[], Awaitable[Any]]) -> Any:
    """Résolution mémorisée pour l'import, rejets compris (un libellé rejeté n'est résolu qu'une fois)."""
    if cle not in cache:
        try:
            cache[cle] = await fabrique()
        except ValueError as exc:
            cache[cle] = exc
    valeur = cache[cle]
    if isinstance(valeur, ValueError):
        raise ValueError(str(valeur))
    return valeur


# ---------------------------------------------------------------------------
# Import principal
# ---------------------------------------------------------------------------


def _can_validate(user: Utilisateur) -> bool:
    try:
        distribution_rules._ensure_can_validate(user)
    except HTTPException:
        return False
    return True


def _http_error_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("error") or detail)
    return str(detail)


async def import_fis_file(
    db: AsyncSession,
    file_bytes: bytes,
    *,
    current_user: Utilisateur,
    skip_existing: bool = True,
    correspondances: dict[tuple[str, str], Any] | None = None,
) -> FisImportResult:
    """Parse le fichier FIS et importe les interruptions en base.

    Args:
        db: session SQLAlchemy async.
        file_bytes: contenu brut du fichier Excel FIS.
        current_user: utilisateur qui déclenche l'import (périmètre + droit de valider).
        skip_existing: si True, ignore les numéros déjà présents dans l'année ; sinon la
            ligne est rejetée (un doublon n'est jamais créé).
        correspondances: correspondances FIS administrées `{(catégorie, libellé normalisé): …}`,
            prioritaires sur la table interne et la recherche par libellé.

    Returns:
        FisImportResult avec statistiques d'import et interruptions créées.
    """
    stats = FisImportStats()
    services_touches: set[str] = set()
    dates: list[datetime] = []
    creees: list[tuple[int, str]] = []
    created_by_id = current_user.id
    statut_import = "valide" if _can_validate(current_user) else "cloture"

    # 1. Parser le fichier (openpyxl est synchrone : hors de la boucle d'événements)
    rows = await asyncio.to_thread(parse_fis_sheet, file_bytes)
    stats.total_lignes = len(rows)

    if not rows:
        return FisImportResult(stats=stats)

    # 2. Caches de résolution (rejets compris)
    nature_cache: dict[str, Any] = {}
    cause_cache: dict[str, Any] = {}
    siege_cache: dict[str, Any] = {}
    signalisation_cache: dict[str, Any] = {}
    service_cache: dict[str, Any] = {}
    feeder_cache: dict[tuple[str, int | None], Any] = {}
    poste_source_cache: dict[str, Any] = {}

    # 3. Importer ligne par ligne — chaque ligne dans un savepoint : une ligne
    #    en erreur est annulée seule, sans laisser d'écriture partielle.
    for row in rows:
        savepoint = None
        try:
            # Doublon : même numéro, distribution, même année
            annee = row.date_apparition.year
            if await _interruption_exists(db, row.numero, annee):
                if skip_existing:
                    stats.doublons_ignores += 1
                    continue
                raise ValueError(f"interruption n° {row.numero} déjà présente en {annee} : doublon non créé")

            # Résolution service
            service = await _en_cache(
                service_cache, _normalise(row.service_libelle), lambda: _find_service(db, row.service_libelle)
            )
            service_id = service.id if service else None

            # Périmètre d'écriture : mêmes règles que la saisie manuelle
            if service_id is None:
                if distribution_rules._read_scope(current_user) is not None:
                    raise ValueError(f"service « {row.service_libelle} » introuvable : périmètre invérifiable")
            else:
                await distribution_rules._ensure_service_in_write_scope(db, current_user, service_id)

            # Résolution feeder, puis poste source : celui du feeder, sinon celui du fichier
            feeder = await _en_cache(
                feeder_cache,
                (_normalise(row.feeder_libelle), service_id, _normalise(row.source_libelle)),
                lambda: _find_feeder(db, row.feeder_libelle, service_id, source_libelle=row.source_libelle),
            )
            if feeder is not None:
                poste_source_id = feeder.poste_source_id
                # Compte national, service du fichier introuvable : celui du feeder (comme la saisie)
                if service_id is None and feeder.service_id is not None:
                    service_id = feeder.service_id
            else:
                poste_source = await _en_cache(
                    poste_source_cache,
                    _normalise(row.source_libelle),
                    lambda: _find_poste_source(db, row.source_libelle),
                )
                poste_source_id = poste_source.id if poste_source else None

            # Référentiel (lu, jamais écrit) : correspondances administrées d'abord
            nature = await _en_cache(
                nature_cache,
                _normalise(row.nature_libelle),
                lambda: _resoudre_nature(db, row.nature_libelle, correspondances),
            )
            cause, is_force_majeure = await _en_cache(
                cause_cache,
                _normalise(row.cause_libelle),
                lambda: _resoudre_cause(db, row.cause_libelle, correspondances),
            )
            siege = await _en_cache(
                siege_cache,
                _normalise(row.siege_libelle),
                lambda: _resoudre_siege(db, row.siege_libelle, correspondances),
            )
            signalisation = await _en_cache(
                signalisation_cache,
                _normalise(row.signalisation_libelle),
                lambda: _resoudre_signalisation_fis(db, row.signalisation_libelle, correspondances),
            )

            # Flags
            nature_code = nature.code if nature else ""
            is_fugitive = nature_code in NATURES_FUGITIVES
            # Même règle que la saisie manuelle (code ou libellé : coupure, travaux, programmée)
            is_programme = nature_code in NATURES_PROGRAMMEES or distribution_rules._nature_programmee(nature)

            # Conversion kW → MW, kWh → MWh
            puissance_mw = row.puissance_kw / 1000.0
            end_mwh = row.end_kwh / 1000.0

            # Région d'exploitation : celle du départ ; un BCC / BRC n'importe que sa région
            region_id = await distribution_rules.repo.region_du_depart(
                db, poste_source_id, service_id, feeder_id=feeder.id if feeder else None
            )
            region_compte = _region_du_compte(current_user)
            if region_compte is not None:
                if region_id is not None and region_id != region_compte:
                    raise ValueError("Hors périmètre : départ d'une autre région que celle du compte")
                region_id = region_compte

            savepoint = await db.begin_nested()

            # Créer l'interruption principale
            interruption = Interruption(
                numero_interruption=row.numero,
                type_direction="distribution",
                statut=statut_import,
                validated_by_id=created_by_id if statut_import == "valide" else None,
                service_id=service_id,
                region_id=region_id,
                feeder_id=feeder.id if feeder else None,
                poste_source_id=poste_source_id,
                date_apparition=row.date_apparition,
                date_remise=row.date_remise,
                duree_minutes=row.duree_minutes if row.duree_minutes > 0 else None,
                cause_id=cause.id if cause else None,
                siege_id=siege.id if siege else None,
                nature_id=nature.id if nature else None,
                signalisation_id=signalisation.id if signalisation else None,
                is_force_majeure=is_force_majeure,
                is_fugitive=is_fugitive,
                puissance_coupee_mw=puissance_mw if puissance_mw > 0 else None,
                localisation=row.troncon,
                observations=row.observations,
                created_by_id=created_by_id,
            )
            db.add(interruption)
            await db.flush()  # obtenir l'id

            # Créer le détail distribution
            distrib = InterruptionDistribution(
                interruption_id=interruption.id,
                tension_kv=row.tension_kv,
                end_mwh=end_mwh if end_mwh > 0 else None,
                is_programme=is_programme,
            )
            db.add(distrib)
            await db.flush()
            await savepoint.commit()

            # Statistiques
            stats.importees += 1
            stats.end_total_kwh += row.end_kwh
            dates.append(row.date_apparition)
            creees.append((interruption.id, statut_import))
            if row.service_libelle:
                services_touches.add(row.service_libelle)

        except HTTPException as exc:
            await _rollback_savepoint(savepoint)
            msg = f"Ligne N°{row.numero}: {_http_error_message(exc)}"
            stats.erreurs += 1
            stats.erreurs_detail.append(msg)
            continue
        except Exception as exc:
            await _rollback_savepoint(savepoint)
            msg = f"Ligne N°{row.numero}: {exc}"
            logger.warning("FIS import error — %s", msg)
            stats.erreurs += 1
            stats.erreurs_detail.append(msg)
            continue

    return FisImportResult(
        stats=stats,
        periode_debut=min(dates) if dates else None,
        periode_fin=max(dates) if dates else None,
        services_touches=sorted(services_touches),
        creees=creees,
    )


# ---------------------------------------------------------------------------
# Orchestration (route POST /interruptions/distribution/import-fis)
# ---------------------------------------------------------------------------

MOTIF_HISTORIQUE = "Import FIS"


async def importer_fis(
    db: AsyncSession,
    contenu: bytes,
    *,
    current_user: Utilisateur,
    skip_existing: bool = True,
) -> FisImportResult:
    """Import FIS complet : correspondances administrées, import, historique des statuts.

    Chaque interruption créée reçoit sa ligne « création » dans l'historique, et une ligne
    « validation » si elle est importée validée — au nom de l'utilisateur qui importe.
    """
    correspondances = await correspondance_fis_repository.dictionnaire(db)
    resultat = await import_fis_file(
        db,
        contenu,
        current_user=current_user,
        skip_existing=skip_existing,
        correspondances=correspondances,
    )
    for interruption_id, statut in resultat.creees:
        await interruption_statut_repository.ajouter(
            db,
            interruption_id=interruption_id,
            action=ACTION_CREATION,
            ancien_statut=None,
            nouveau_statut=statut,
            utilisateur_id=current_user.id,
            motif=MOTIF_HISTORIQUE,
        )
        if statut == "valide":
            await interruption_statut_repository.ajouter(
                db,
                interruption_id=interruption_id,
                action=ACTION_VALIDATION,
                ancien_statut="cloture",
                nouveau_statut="valide",
                utilisateur_id=current_user.id,
                motif=MOTIF_HISTORIQUE,
            )
    return resultat
