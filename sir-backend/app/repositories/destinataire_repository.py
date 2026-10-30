"""Repository — destinataires notifications."""

from sqlalchemy import Select, and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Agence, Delegation, Service
from app.models.notifications import Destinataire, GroupeEnvoi


def _service_ids_in_region_subquery(region_id: int) -> Select[tuple[int]]:
    return (
        select(Service.id)
        .join(Agence, Service.agence_id == Agence.id)
        .join(Delegation, Agence.delegation_id == Delegation.id)
        .where(Delegation.region_id == region_id)
    )


async def get_by_id(db: AsyncSession, destinataire_id: int) -> Destinataire | None:
    result = await db.execute(select(Destinataire).where(Destinataire.id == destinataire_id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    nom: str,
    telephone: str | None,
    email: str | None,
    utilisateur_id: int | None,
    service_id: int | None,
    fonction: str | None = None,
    groupe_id: int | None = None,
) -> Destinataire:
    record = Destinataire(
        nom=nom,
        telephone=telephone,
        email=email,
        utilisateur_id=utilisateur_id,
        service_id=service_id,
        fonction=fonction,
        groupe_id=groupe_id,
        is_active=True,
    )
    db.add(record)
    await db.flush()
    return record


async def update(db: AsyncSession, record: Destinataire, **fields: object) -> Destinataire:
    for key, value in fields.items():
        if value is not None or key == "is_active":
            setattr(record, key, value)
    await db.flush()
    return record


def build_list_query(
    *,
    service_id: int | None,
    is_active: bool | None,
    service_ids_scope: list[int] | None,
    region_id_scope: int | None,
    force_service_id: int | None,
) -> Select[tuple[Destinataire]]:
    query = select(Destinataire).order_by(Destinataire.id)

    if is_active is not None:
        query = query.where(Destinataire.is_active == is_active)

    if force_service_id is not None:
        query = query.where(Destinataire.service_id == force_service_id)
    elif service_id is not None:
        query = query.where(Destinataire.service_id == service_id)
    elif service_ids_scope is not None:
        if not service_ids_scope:
            query = query.where(Destinataire.id == -1)
        else:
            query = query.where(Destinataire.service_id.in_(service_ids_scope))
    elif region_id_scope is not None:
        query = query.where(Destinataire.service_id.in_(_service_ids_in_region_subquery(region_id_scope)))

    return query


async def list_active_for_service(db: AsyncSession, service_id: int) -> list[Destinataire]:
    result = await db.execute(
        select(Destinataire).where(
            Destinataire.is_active == true(),
            Destinataire.service_id == service_id,
        )
    )
    return list(result.scalars().all())


async def get_by_utilisateur_id(db: AsyncSession, utilisateur_id: int) -> Destinataire | None:
    result = await db.execute(
        select(Destinataire).where(
            Destinataire.utilisateur_id == utilisateur_id,
            Destinataire.is_active == true(),
        )
    )
    return result.scalar_one_or_none()


async def list_actifs_avec_email(db: AsyncSession) -> list[Destinataire]:
    """Destinataires des rapports planifiés : actifs et joignables par e-mail."""
    result = await db.execute(
        select(Destinataire)
        .where(
            Destinataire.is_active == true(),
            Destinataire.email.is_not(None),
            Destinataire.email != "",
        )
        .order_by(Destinataire.id)
    )
    return list(result.scalars().all())


async def list_groupes_envoi(db: AsyncSession, query_destinataires: Select[tuple[Destinataire]]) -> list[tuple[int, str, int]]:
    """Groupes actifs avec le nombre de destinataires actifs avec téléphone dans le périmètre."""
    perimetre = query_destinataires.with_only_columns(Destinataire.id).order_by(None).subquery()
    stmt = (
        select(GroupeEnvoi.id, GroupeEnvoi.libelle, func.count(Destinataire.id))
        .outerjoin(
            Destinataire,
            and_(
                Destinataire.groupe_id == GroupeEnvoi.id,
                Destinataire.is_active == true(),
                Destinataire.telephone.is_not(None),
                Destinataire.id.in_(select(perimetre.c.id)),
            ),
        )
        .where(GroupeEnvoi.is_active == true())
        .group_by(GroupeEnvoi.id, GroupeEnvoi.libelle)
        .order_by(GroupeEnvoi.libelle)
    )
    return [(int(i), str(lib), int(n)) for i, lib, n in (await db.execute(stmt)).all()]
