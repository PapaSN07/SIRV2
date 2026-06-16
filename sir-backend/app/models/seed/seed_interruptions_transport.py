"""Seeder interruptions transport / OMVG — jeu minimal dev.

Prérequis : seed_rbac exécuté · équipements transport créés via ce seeder.

Usage :
    from app.models.seed.seed_interruptions_transport import seed_interruptions_transport
    await seed_interruptions_transport(db)
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.interruptions import Interruption, InterruptionTransport
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.reseau import EquipementTransport, SourceTransport
from app.models.utilisateurs import Role, UserRole, Utilisateur

_SEED_MARKER = "SEED-TR:"

_REFERENTIEL: list[tuple[str, type, str, str]] = [
    ("CAUSE-TR", Cause, "Défaut ligne HTB", "transport"),
    ("SIEGE-TR", Siege, "Poste HTB", "transport"),
    ("SIG-TR", Signalisation, "Signalisation HTB", "transport"),
    ("NAT-TR", Nature, "Incident transport", ""),
]

_EQUIP_CODE = "EQ-HTB-01"
_SOURCE_CODE = "SRC-HTB-01"
_DISPATCHER_LOGIN = "dispatcher.dev"

_INTERRUPTIONS: list[dict[str, object]] = [
    {
        "marker": "HTB-EN-COURS",
        "type_direction": "transport",
        "numero": 2026101,
        "statut": "en_cours",
    },
    {
        "marker": "OMVG-EN-COURS",
        "type_direction": "omvg",
        "numero": 2026101,
        "statut": "en_cours",
    },
]


async def _upsert_referentiel(
    db: AsyncSession,
) -> tuple[Cause, Siege, Signalisation, Nature]:
    cause = siege = sig = nature = None
    for code, model, libelle, type_reseau in _REFERENTIEL:
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
            cause = row
        elif model is Siege:
            siege = row
        elif model is Signalisation:
            sig = row
        elif model is Nature:
            nature = row
    assert cause and siege and sig and nature
    return cause, siege, sig, nature


async def _upsert_equipement(db: AsyncSession) -> EquipementTransport:
    result = await db.execute(
        select(EquipementTransport).where(EquipementTransport.code == _EQUIP_CODE)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = EquipementTransport(
        code=_EQUIP_CODE,
        libelle="Ligne HTB Yoff-Tivaouane",
        type_equipement="ligne",
        tension_kv=225.0,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _upsert_source(db: AsyncSession) -> SourceTransport:
    result = await db.execute(
        select(SourceTransport).where(SourceTransport.code == _SOURCE_CODE)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    row = SourceTransport(
        code=_SOURCE_CODE,
        libelle="Centrale Cap des Biches",
        puissance_mw=150.0,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _upsert_dispatcher(db: AsyncSession) -> Utilisateur:
    result = await db.execute(select(Utilisateur).where(Utilisateur.login == _DISPATCHER_LOGIN))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    role_result = await db.execute(select(Role).where(Role.nom == "DISPATCHER"))
    role = role_result.scalar_one_or_none()
    if role is None:
        raise ValueError("Rôle DISPATCHER introuvable — exécuter seed_rbac d'abord")

    user = Utilisateur(
        login=_DISPATCHER_LOGIN,
        password_hash=hash_password("DevSir123!"),
        nom="Dispatcher",
        prenom="Dev",
        email=f"{_DISPATCHER_LOGIN}@senelec.sn",
        telephone=None,
        is_active=True,
        premiere_connexion=False,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(utilisateur_id=user.id, role_id=role.id, scope_service_id=None))
    await db.flush()
    return user


async def _find_by_marker(
    db: AsyncSession,
    marker: str,
    type_direction: str,
) -> Interruption | None:
    result = await db.execute(
        select(Interruption).where(
            Interruption.observations == f"{_SEED_MARKER}{marker}",
            Interruption.type_direction == type_direction,
        )
    )
    return result.scalar_one_or_none()


async def seed_interruptions_transport(db: AsyncSession) -> None:
    """Charge référentiel transport + 2 interruptions (HTB + OMVG, numéros indépendants)."""
    cause, siege, sig, nature = await _upsert_referentiel(db)
    equipement = await _upsert_equipement(db)
    source = await _upsert_source(db)
    dispatcher = await _upsert_dispatcher(db)

    date_apparition = datetime(2026, 6, 12, 8, 0, 0)

    for spec in _INTERRUPTIONS:
        marker = str(spec["marker"])
        type_direction = str(spec["type_direction"])
        existing = await _find_by_marker(db, marker, type_direction)
        if existing is not None:
            continue

        interruption = Interruption(
            numero_interruption=int(spec["numero"]),  # type: ignore[arg-type]
            type_direction=type_direction,
            statut=str(spec["statut"]),
            service_id=None,
            date_apparition=date_apparition,
            cause_id=cause.id,
            nature_id=nature.id,
            siege_id=siege.id,
            signalisation_id=sig.id,
            puissance_coupee_mw=50.0,
            observations=f"{_SEED_MARKER}{marker}",
            is_force_majeure=False,
            is_fugitive=False,
            created_by_id=dispatcher.id,
        )
        db.add(interruption)
        await db.flush()

        db.add(
            InterruptionTransport(
                interruption_id=interruption.id,
                equipement_transport_id=equipement.id,
                source_transport_id=source.id,
                tension_kv=225.0,
                puissance_transit_mw=120.0,
            )
        )
        await db.flush()

    await db.flush()
