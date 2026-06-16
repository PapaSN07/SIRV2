"""Seeder indicateurs dev — nombre_client_mois, energie_nd, saifi_saidi.

Prérequis : seed_rbac, seed_geo, seed_reseau, seed_interruptions.

Usage :
    from app.models.seed.seed_indicateurs import seed_indicateurs
    await seed_indicateurs(db)
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.geo import Service
from app.models.indicateurs import EnergieNd, NombreClientMois, SaifiSaidi
from app.models.interruptions import Interruption
from app.models.utilisateurs import Role, UserRole, Utilisateur

_SEED_MARKER = "SEED:"
_DEV_SAQS_LOGIN = "saqs.dev"
_ANNEE = 2026
_MOIS = 6

_CLIENTS_PAR_SERVICE: list[tuple[str, int]] = [
    ("SVC-DKR-01", 50_000),
    ("SVC-THS-01", 30_000),
]

_DEMO_SAIFI_SAIDI: list[tuple[str, float, float, int]] = [
    ("SVC-DKR-01", 0.0024, 0.048, 1),
    ("SVC-THS-01", 0.0015, 0.030, 1),
]


async def _get_by_code(db: AsyncSession, model: type, code: str):
    result = await db.execute(select(model).where(model.code == code))  # type: ignore[attr-defined]
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"{model.__name__} '{code}' introuvable — exécuter les seeds prérequis")
    return row


async def _find_interruption_by_marker(db: AsyncSession, marker: str) -> Interruption | None:
    result = await db.execute(
        select(Interruption).where(
            Interruption.observations == f"{_SEED_MARKER}{marker}",
            Interruption.type_direction == "distribution",
        )
    )
    return result.scalar_one_or_none()


async def _upsert_nombre_client_mois(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
    nombre_clients: int,
) -> None:
    result = await db.execute(
        select(NombreClientMois).where(
            NombreClientMois.service_id == service_id,
            NombreClientMois.annee == annee,
            NombreClientMois.mois == mois,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.nombre_clients = nombre_clients
        await db.flush()
        return

    db.add(
        NombreClientMois(
            service_id=service_id,
            annee=annee,
            mois=mois,
            nombre_clients=nombre_clients,
        )
    )
    await db.flush()


async def _upsert_energie_nd_for_interruption(
    db: AsyncSession,
    interruption: Interruption,
    *,
    valeur_mwh: float,
) -> None:
    result = await db.execute(
        select(EnergieNd).where(EnergieNd.interruption_id == interruption.id)
    )
    existing = result.scalar_one_or_none()
    duree_h = (interruption.duree_minutes or 0) / 60
    puissance = float(interruption.puissance_coupee_mw or 0)

    if existing is not None:
        existing.valeur_mwh = valeur_mwh
        existing.puissance_coupee_mw = puissance
        existing.duree_heures = duree_h
        existing.est_force_majeure = interruption.is_force_majeure
        existing.calculated_at = datetime.now()
        await db.flush()
        return

    db.add(
        EnergieNd(
            interruption_id=interruption.id,
            type_end_id=None,
            valeur_mwh=valeur_mwh,
            puissance_coupee_mw=puissance,
            duree_heures=duree_h,
            est_force_majeure=interruption.is_force_majeure,
            calculated_at=datetime.now(),
        )
    )
    await db.flush()


async def _upsert_saifi_saidi(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
    saifi: float,
    saidi: float,
    nombre_interruptions: int,
    total_clients_reference: int,
) -> None:
    result = await db.execute(
        select(SaifiSaidi).where(
            SaifiSaidi.service_id == service_id,
            SaifiSaidi.annee == annee,
            SaifiSaidi.mois == mois,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.saifi = saifi
        existing.saidi = saidi
        existing.nombre_interruptions = nombre_interruptions
        existing.total_clients_reference = total_clients_reference
        existing.calculated_at = datetime.now()
        await db.flush()
        return

    db.add(
        SaifiSaidi(
            service_id=service_id,
            annee=annee,
            mois=mois,
            saifi=saifi,
            saidi=saidi,
            nombre_interruptions=nombre_interruptions,
            total_clients_reference=total_clients_reference,
            calculated_at=datetime.now(),
        )
    )
    await db.flush()


async def _upsert_dev_saqs_user(db: AsyncSession) -> Utilisateur:
    result = await db.execute(select(Utilisateur).where(Utilisateur.login == _DEV_SAQS_LOGIN))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    role_result = await db.execute(select(Role).where(Role.nom == "ADMIN_SAQS"))
    role = role_result.scalar_one_or_none()
    if role is None:
        raise ValueError("Rôle ADMIN_SAQS introuvable — exécuter seed_rbac d'abord")

    user = Utilisateur(
        login=_DEV_SAQS_LOGIN,
        password_hash=hash_password("DevSir123!"),
        nom="SAQS Dev",
        prenom="Admin",
        email=f"{_DEV_SAQS_LOGIN}@senelec.sn",
        telephone=None,
        is_active=True,
        premiere_connexion=False,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(utilisateur_id=user.id, role_id=role.id, scope_service_id=None))
    await db.flush()
    return user


async def seed_indicateurs(db: AsyncSession) -> None:
    """Charge snapshots clients, energie_nd de démo et agrégats SAIFI/SAIDI."""
    await _upsert_dev_saqs_user(db)

    for service_code, nombre_clients in _CLIENTS_PAR_SERVICE:
        service: Service = await _get_by_code(db, Service, service_code)
        await _upsert_nombre_client_mois(
            db,
            service_id=service.id,
            annee=_ANNEE,
            mois=_MOIS,
            nombre_clients=nombre_clients,
        )

    end_by_marker = {
        "INT-CLOTURE": 2.5,
        "INT-VALIDE": 1.8,
    }
    for marker, end_mwh in end_by_marker.items():
        interruption = await _find_interruption_by_marker(db, marker)
        if interruption is not None:
            await _upsert_energie_nd_for_interruption(
                db, interruption, valeur_mwh=end_mwh
            )

    for service_code, saifi, saidi, nb in _DEMO_SAIFI_SAIDI:
        service = await _get_by_code(db, Service, service_code)
        total_clients = next(
            n for code, n in _CLIENTS_PAR_SERVICE if code == service_code
        )
        await _upsert_saifi_saidi(
            db,
            service_id=service.id,
            annee=_ANNEE,
            mois=_MOIS,
            saifi=saifi,
            saidi=saidi,
            nombre_interruptions=nb,
            total_clients_reference=total_clients,
        )

    await db.flush()
