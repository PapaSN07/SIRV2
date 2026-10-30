"""Repository — destinataires notifications."""

from sqlalchemy import Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Agence, Delegation, Service
from app.models.notifications import Destinataire, GroupeEnvoi, destinataire_groupes


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
    matricule: int | None = None,
    groupes: list[GroupeEnvoi] | None = None,
) -> Destinataire:
    record = Destinataire(
        nom=nom,
        telephone=telephone,
        email=email,
        utilisateur_id=utilisateur_id,
        service_id=service_id,
        fonction=fonction,
        matricule=matricule,
        is_active=True,
    )
    record.groupes = list(groupes or [])
    db.add(record)
    await db.flush()
    return record


_NON_VIDABLES = frozenset({"nom", "is_active"})


async def update(db: AsyncSession, record: Destinataire, **fields: object) -> Destinataire:
    """Applique les champs transmis ; ``None`` vide un champ facultatif (service, fonction…)."""
    for key, value in fields.items():
        if value is None and key in _NON_VIDABLES:
            continue
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
    groupe_id: int | None = None,
    recherche: str | None = None,
) -> Select[tuple[Destinataire]]:
    query = select(Destinataire).order_by(Destinataire.nom, Destinataire.id)

    if groupe_id is not None:
        query = query.where(
            Destinataire.id.in_(
                select(destinataire_groupes.c.destinataire_id).where(destinataire_groupes.c.groupe_id == groupe_id)
            )
        )
    if recherche:
        motif = f"%{recherche.strip()}%"
        query = query.where(
            or_(Destinataire.nom.ilike(motif), Destinataire.telephone.ilike(motif), Destinataire.fonction.ilike(motif))
        )

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



async def list_groupes_envoi(
    db: AsyncSession,
    query_destinataires: Select[tuple[Destinataire]],
    *,
    inclure_inactifs: bool = False,
) -> list[tuple[GroupeEnvoi, int]]:
    """Groupes avec le nombre de destinataires actifs avec téléphone dans le périmètre."""
    perimetre = query_destinataires.with_only_columns(Destinataire.id).order_by(None).subquery()
    membres = (
        select(destinataire_groupes.c.groupe_id, func.count(Destinataire.id).label("nb"))
        .join(Destinataire, Destinataire.id == destinataire_groupes.c.destinataire_id)
        .where(
            Destinataire.is_active == true(),
            Destinataire.telephone.is_not(None),
            Destinataire.id.in_(select(perimetre.c.id)),
        )
        .group_by(destinataire_groupes.c.groupe_id)
        .subquery()
    )
    stmt = (
        select(GroupeEnvoi, func.coalesce(membres.c.nb, 0))
        .outerjoin(membres, membres.c.groupe_id == GroupeEnvoi.id)
        .order_by(GroupeEnvoi.libelle)
    )
    if not inclure_inactifs:
        stmt = stmt.where(GroupeEnvoi.is_active == true())
    return [(g, int(n)) for g, n in (await db.execute(stmt)).all()]


async def get_groupes(db: AsyncSession, ids: list[int]) -> list[GroupeEnvoi]:
    if not ids:
        return []
    rows = await db.execute(select(GroupeEnvoi).where(GroupeEnvoi.id.in_(ids)))
    return list(rows.scalars().all())


async def get_groupe(db: AsyncSession, groupe_id: int) -> GroupeEnvoi | None:
    return (await db.execute(select(GroupeEnvoi).where(GroupeEnvoi.id == groupe_id))).scalar_one_or_none()


async def get_groupe_par_libelle(db: AsyncSession, libelle: str) -> GroupeEnvoi | None:
    return (await db.execute(select(GroupeEnvoi).where(GroupeEnvoi.libelle == libelle))).scalar_one_or_none()


async def create_groupe(db: AsyncSession, *, libelle: str, exploitation: str | None) -> GroupeEnvoi:
    groupe = GroupeEnvoi(libelle=libelle, exploitation=exploitation, is_active=True)
    db.add(groupe)
    await db.flush()
    return groupe


async def compter_membres(db: AsyncSession, groupe_id: int) -> int:
    stmt = select(func.count()).select_from(destinataire_groupes).where(destinataire_groupes.c.groupe_id == groupe_id)
    return int((await db.execute(stmt)).scalar_one())
