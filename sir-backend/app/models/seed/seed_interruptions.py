"""Seeder interruptions distribution — jeu minimal dev.

Prérequis : seed_rbac, seed_geo, seed_reseau exécutés avant.

Usage :
    from app.models.seed.seed_interruptions import seed_interruptions
    await seed_interruptions(db)
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.geo import Service
from app.models.interruptions import (
    Interruption,
    InterruptionDistribution,
    PosteInterruption,
)
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.reseau import Feeder, Poste, PosteSource
from app.models.utilisateurs import Role, UserRole, Utilisateur

_SEED_MARKER = "SEED:"

_REFERENTIEL: list[tuple[str, type, str, str, str | None]] = [
    # (code, model, libelle, type_reseau_or_empty, _)
    ("CAUSE-DEF", Cause, "Défaut équipement", "distribution", None),
    ("CAUSE-OR", Cause, "Défaut organique", "distribution", None),
    ("CAUSE-EXT", Cause, "Facteur exogène", "distribution", None),
    ("SIEGE-DEF", Siege, "Ligne MT", "distribution", None),
    ("SIG-DEF", Signalisation, "Signalisation standard", "distribution", None),
]

_INTERRUPTIONS: list[dict[str, object]] = [
    {
        "marker": "INT-EN-COURS",
        "statut": "en_cours",
        "numero": 2026001,
        "date_apparition": datetime(2026, 6, 10, 8, 0, 0),
        "date_remise": None,
        "duree_minutes": None,
        "with_poste": True,
        "validated_by_id": None,
        "end_mwh": None,
        "cause_code": "CAUSE-DEF",
        "nature_code": "PERMANENT",
    },
    {
        "marker": "INT-CLOTURE",
        "statut": "cloture",
        "numero": 2026002,
        "date_apparition": datetime(2026, 6, 8, 14, 0, 0),
        "date_remise": datetime(2026, 6, 8, 16, 30, 0),
        "duree_minutes": 150,
        "with_poste": True,
        "validated_by_id": None,
        "end_mwh": 2.5,
        "cause_code": "CAUSE-OR",
        "nature_code": "FUGITIF",
    },
    {
        "marker": "INT-VALIDE",
        "statut": "valide",
        "numero": 2026003,
        "date_apparition": datetime(2026, 6, 5, 9, 0, 0),
        "date_remise": datetime(2026, 6, 5, 11, 0, 0),
        "duree_minutes": 120,
        "with_poste": True,
        "validated_by_id": "supervisor",
        "end_mwh": 1.8,
        "cause_code": "CAUSE-EXT",
        "nature_code": "DELESTAGE",
    },
]

_DEV_BCC_LOGIN = "bcc.dev"
_DEV_SUP_LOGIN = "superviseur.dev"
_FEEDER_CODE = "FD-DKR-01"
_POSTE_CODE = "PT-DKR-01"
_SERVICE_CODE = "SVC-DKR-01"
_POSTE_SOURCE_CODE = "PS-DKR-01"


async def _get_by_code(db: AsyncSession, model: type, code: str):
    result = await db.execute(select(model).where(model.code == code))  # type: ignore[attr-defined]
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"{model.__name__} '{code}' introuvable — exécuter les seeds prérequis")
    return row


async def _upsert_referentiel(db: AsyncSession) -> tuple[Cause, Siege, Signalisation]:
    causes: dict[str, Cause] = {}
    siege = sig = None
    for code, model, libelle, type_reseau, _ in _REFERENTIEL:
        result = await db.execute(select(model).where(model.code == code))  # type: ignore[arg-type]
        row = result.scalar_one_or_none()
        if row is None:
            kwargs: dict[str, object] = {"code": code, "libelle": libelle, "is_active": True}
            if type_reseau:
                kwargs["type_reseau"] = type_reseau
            row = model(**kwargs)  # type: ignore[call-arg,misc]
            db.add(row)
            await db.flush()
        if model is Cause:
            causes[code] = row
        elif model is Siege:
            siege = row
        elif model is Signalisation:
            sig = row
    assert siege and sig and causes
    return causes, siege, sig


async def _get_nature_by_code(db: AsyncSession, code: str) -> Nature:
    result = await db.execute(select(Nature).where(Nature.code == code))
    nature = result.scalar_one_or_none()
    if nature is None:
        raise ValueError(
            f"Nature '{code}' introuvable — exécuter seed_natures avant seed_interruptions"
        )
    return nature


async def _upsert_dev_user(
    db: AsyncSession,
    *,
    login: str,
    role_nom: str,
    scope_service_id: int,
    nom: str,
) -> Utilisateur:
    result = await db.execute(select(Utilisateur).where(Utilisateur.login == login))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    role_result = await db.execute(select(Role).where(Role.nom == role_nom))
    role = role_result.scalar_one_or_none()
    if role is None:
        raise ValueError(f"Rôle '{role_nom}' introuvable — exécuter seed_rbac d'abord")

    user = Utilisateur(
        login=login,
        password_hash=hash_password("DevSir123!"),
        nom=nom,
        prenom="Dev",
        email=f"{login}@senelec.sn",
        telephone=None,
        is_active=True,
        premiere_connexion=False,
    )
    db.add(user)
    await db.flush()

    db.add(
        UserRole(
            utilisateur_id=user.id,
            role_id=role.id,
            scope_service_id=scope_service_id,
        )
    )
    await db.flush()
    return user


async def _find_by_marker(db: AsyncSession, marker: str) -> Interruption | None:
    result = await db.execute(
        select(Interruption).where(
            Interruption.observations == f"{_SEED_MARKER}{marker}",
            Interruption.type_direction == "distribution",
        )
    )
    return result.scalar_one_or_none()


async def _upsert_interruption(
    db: AsyncSession,
    *,
    marker: str,
    statut: str,
    numero: int,
    date_apparition: datetime,
    date_remise: datetime | None,
    duree_minutes: int | None,
    service_id: int,
    feeder_id: int,
    poste_source_id: int,
    cause_id: int,
    nature_id: int,
    siege_id: int,
    signalisation_id: int,
    created_by_id: int,
    validated_by_id: int | None,
    end_mwh: float | None,
    with_poste: bool,
    poste_id: int,
) -> Interruption:
    existing = await _find_by_marker(db, marker)
    if existing is not None:
        return existing

    interruption = Interruption(
        numero_interruption=numero,
        type_direction="distribution",
        statut=statut,
        service_id=service_id,
        feeder_id=feeder_id,
        poste_source_id=poste_source_id,
        date_apparition=date_apparition,
        date_remise=date_remise,
        duree_minutes=duree_minutes,
        cause_id=cause_id,
        nature_id=nature_id,
        siege_id=siege_id,
        signalisation_id=signalisation_id,
        puissance_coupee_mw=2.0,
        observations=f"{_SEED_MARKER}{marker}",
        is_force_majeure=False,
        is_fugitive=False,
        created_by_id=created_by_id,
        validated_by_id=validated_by_id,
    )
    db.add(interruption)
    await db.flush()

    distribution = InterruptionDistribution(
        interruption_id=interruption.id,
        tension_kv=30.0,
        nombre_clients_mt=50,
        nombre_clients_bt=200,
        end_mwh=end_mwh,
        is_programme=False,
        has_extension_bt=False,
    )
    db.add(distribution)
    await db.flush()

    if with_poste:
        db.add(
            PosteInterruption(
                interruption_id=interruption.id,
                poste_id=poste_id,
                nombre_clients_touches=120,
                feeder_id=feeder_id,
                service_id=service_id,
                poste_source_id=poste_source_id,
            )
        )
        await db.flush()

    return interruption


async def seed_interruptions(db: AsyncSession) -> None:
    """Charge référentiel minimal + 3 interruptions distribution (en_cours, cloture, valide)."""
    service: Service = await _get_by_code(db, Service, _SERVICE_CODE)
    feeder: Feeder = await _get_by_code(db, Feeder, _FEEDER_CODE)
    poste: Poste = await _get_by_code(db, Poste, _POSTE_CODE)
    poste_source: PosteSource = await _get_by_code(db, PosteSource, _POSTE_SOURCE_CODE)

    causes, siege, sig = await _upsert_referentiel(db)

    bcc_result = await db.execute(select(Utilisateur).where(Utilisateur.login == _DEV_BCC_LOGIN))
    bcc = bcc_result.scalar_one_or_none()
    if bcc is None:
        raise ValueError(f"Utilisateur '{_DEV_BCC_LOGIN}' introuvable — exécuter seed_dev_accounts d'abord")

    supervisor = await _upsert_dev_user(
        db,
        login=_DEV_SUP_LOGIN,
        role_nom="SUPERVISEUR",
        scope_service_id=service.id,
        nom="Superviseur Dev",
    )

    for spec in _INTERRUPTIONS:
        validated_id: int | None = None
        if spec["validated_by_id"] == "supervisor":
            validated_id = supervisor.id

        cause_code = str(spec["cause_code"])
        nature_code = str(spec["nature_code"])
        cause = causes[cause_code]
        nature = await _get_nature_by_code(db, nature_code)

        await _upsert_interruption(
            db,
            marker=str(spec["marker"]),
            statut=str(spec["statut"]),
            numero=int(spec["numero"]),  # type: ignore[arg-type]
            date_apparition=spec["date_apparition"],  # type: ignore[arg-type]
            date_remise=spec["date_remise"],  # type: ignore[arg-type]
            duree_minutes=spec["duree_minutes"],  # type: ignore[arg-type]
            service_id=service.id,
            feeder_id=feeder.id,
            poste_source_id=poste_source.id,
            cause_id=cause.id,
            nature_id=nature.id,
            siege_id=siege.id,
            signalisation_id=sig.id,
            created_by_id=bcc.id,
            validated_by_id=validated_id,
            end_mwh=spec["end_mwh"],  # type: ignore[arg-type]
            with_poste=bool(spec["with_poste"]),
            poste_id=poste.id,
        )

    await db.flush()
