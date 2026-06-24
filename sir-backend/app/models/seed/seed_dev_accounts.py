"""Comptes dev BCC / BRC — idempotent.

Usage :
    from app.models.seed.seed_dev_accounts import seed_dev_accounts
    await seed_dev_accounts(db)
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.core.security import hash_password
from app.repositories.geo_scope_repository import get_region_id_for_service
from app.models.geo import Region, Service
from app.models.interruptions import Interruption
from app.models.utilisateurs import Role, UserRole, Utilisateur

_DEV_PASSWORD = "DevSir123!"

_DEV_ACCOUNTS: tuple[dict[str, str], ...] = (
    {
        "login": "bcc.dev",
        "role": "BCC",
        "nom": "BCC Dev",
        "scope_kind": "region_by_service",
        "scope_code": "SVC-DKR-01",
    },
    {
        "login": "brc.dev",
        "role": "BRC",
        "nom": "BRC Dev",
        "scope_kind": "region_by_service",
        "scope_code": "SVC-THS-01",
    },
)


async def _fetch_one_or_none(result):
    """Consomme le curseur ODBC (évite « connexion occupée » sur SQL Server)."""
    try:
        return result.scalar_one_or_none()
    finally:
        close = getattr(result, "close", None)
        if close is not None:
            closed = close()
            if asyncio.iscoroutine(closed):
                await closed


async def _resolve_service_id(db: AsyncSession, code: str) -> int:
    result = await db.execute(
        select(Service.id).where(Service.code == code, Service.is_active == True)  # noqa: E712
    )
    service_id = await _fetch_one_or_none(result)
    if service_id is not None:
        return int(service_id)

    top = await db.execute(
        select(Interruption.service_id, func.count().label("cnt"))
        .where(
            Interruption.type_direction == "distribution",
            Interruption.service_id.is_not(None),
        )
        .group_by(Interruption.service_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    row = top.first()
    await top.close()
    if row is not None and row[0] is not None:
        return int(row[0])

    fallback_result = await db.execute(
        select(Service.id).where(Service.is_active == True).order_by(Service.id).limit(1)  # noqa: E712
    )
    fid = await _fetch_one_or_none(fallback_result)
    if fid is None:
        raise ValueError("Aucun service actif — exécuter seed_geo ou vérifier la base")
    return int(fid)


async def _resolve_region_id_from_service_code(db: AsyncSession, code: str) -> int:
    """Région d'un compte BCC/BRC via services.region_id (service métier de référence)."""
    svc_result = await db.execute(
        select(Service.id).where(Service.code == code, Service.is_active == True)  # noqa: E712
    )
    service_id = await _fetch_one_or_none(svc_result)
    if service_id is not None:
        region_id = await get_region_id_for_service(db, int(service_id))
        if region_id is not None:
            return int(region_id)

    return await _resolve_region_id(db, "REG-DKR")


async def _resolve_region_id(db: AsyncSession, code: str) -> int:
    result = await db.execute(
        select(Region.id).where(Region.code == code, Region.is_active == True)  # noqa: E712
    )
    region_id = await _fetch_one_or_none(result)
    if region_id is not None:
        return int(region_id)

    top = await db.execute(
        text("""
            SELECT TOP 1 d.region_id
            FROM dbo.interruptions i
            JOIN dbo.services s ON s.id = i.service_id
            JOIN dbo.agences a ON a.id = s.agence_id
            JOIN dbo.delegations d ON d.id = a.delegation_id
            WHERE i.type_direction = 'distribution'
            GROUP BY d.region_id
            ORDER BY COUNT(*) DESC
        """)
    )
    row = top.first()
    await top.close()
    if row is not None and row[0] is not None:
        return int(row[0])

    fallback_result = await db.execute(
        select(Region.id).where(Region.is_active == True).order_by(Region.id).limit(1)  # noqa: E712
    )
    fid = await _fetch_one_or_none(fallback_result)
    if fid is None:
        raise ValueError("Aucune région active — exécuter seed_geo ou vérifier la base")
    return int(fid)


async def _ensure_dev_user(
    db: AsyncSession,
    *,
    login: str,
    role_nom: str,
    scope_id: int,
    nom: str,
) -> Utilisateur:
    role_result = await db.execute(
        select(Role).options(noload(Role.role_permissions)).where(Role.nom == role_nom)
    )
    role = await _fetch_one_or_none(role_result)
    if role is None:
        raise ValueError(f"Rôle '{role_nom}' introuvable — exécuter seed_rbac d'abord")

    user_result = await db.execute(
        select(Utilisateur)
        .options(noload(Utilisateur.user_roles))
        .where(Utilisateur.login == login)
    )
    user = await _fetch_one_or_none(user_result)

    if user is None:
        user = Utilisateur(
            login=login,
            password_hash=hash_password(_DEV_PASSWORD),
            nom=nom,
            prenom="Dev",
            email=f"{login}@senelec.sn",
            telephone=None,
            is_active=True,
            premiere_connexion=False,
        )
        db.add(user)
        await db.flush()

    ur_result = await db.execute(
        select(UserRole).where(
            UserRole.utilisateur_id == user.id,
            UserRole.role_id == role.id,
        )
    )
    matching = await _fetch_one_or_none(ur_result)
    if matching is None:
        db.add(
            UserRole(
                utilisateur_id=user.id,
                role_id=role.id,
                scope_service_id=scope_id,
            )
        )
    elif matching.scope_service_id != scope_id:
        matching.scope_service_id = scope_id

    await db.flush()
    return user


async def seed_dev_accounts(db: AsyncSession) -> dict[str, dict[str, int | str]]:
    """Crée ou met à jour bcc.dev et brc.dev avec périmètre dev."""
    summary: dict[str, dict[str, int | str]] = {}

    for spec in _DEV_ACCOUNTS:
        scope_kind = spec["scope_kind"]
        scope_code = spec["scope_code"]
        if scope_kind == "service":
            scope_id = await _resolve_service_id(db, scope_code)
        elif scope_kind == "region_by_service":
            scope_id = await _resolve_region_id_from_service_code(db, scope_code)
            scope_kind = "region"
        else:
            scope_id = await _resolve_region_id(db, scope_code)

        user = await _ensure_dev_user(
            db,
            login=spec["login"],
            role_nom=spec["role"],
            scope_id=scope_id,
            nom=spec["nom"],
        )
        summary[spec["login"]] = {
            "user_id": user.id,
            "role": spec["role"],
            "scope_kind": scope_kind,
            "scope_id": scope_id,
        }

    return summary
