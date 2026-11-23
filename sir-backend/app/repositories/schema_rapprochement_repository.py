"""Accès aux données du rapprochement Schéma unifilaire / SIG / SIR et des postes à créer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import bindparam, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only

from app.models.reseau import Feeder, Poste
from app.models.schema_unifilaire import PosteACreer, SchemaUnifilaire, SchemaUnifilairePoste
from app.models.sig import NoeudSig


async def postes(db: AsyncSession, schema_id: int) -> list[SchemaUnifilairePoste]:
    """Postes du schéma avec leur poste SIR (feeder, poste source) et leur nœud SIG."""
    result = await db.execute(
        select(SchemaUnifilairePoste)
        .options(
            load_only(
                SchemaUnifilairePoste.id,
                SchemaUnifilairePoste.schema_id,
                SchemaUnifilairePoste.rang,
                SchemaUnifilairePoste.libelle,
                SchemaUnifilairePoste.poste_id,
                SchemaUnifilairePoste.rapprochement,
                SchemaUnifilairePoste.noeud_sig_id,
                SchemaUnifilairePoste.rapprochement_sig,
                SchemaUnifilairePoste.statut_sir,
            ),
            joinedload(SchemaUnifilairePoste.poste)
            .load_only(Poste.id, Poste.code, Poste.libelle, Poste.feeder_id)
            .joinedload(Poste.feeder)
            .load_only(Feeder.id, Feeder.libelle, Feeder.poste_source_id)
            .joinedload(Feeder.poste_source),
            joinedload(SchemaUnifilairePoste.noeud_sig).load_only(
                NoeudSig.id, NoeudSig.nom, NoeudSig.nom_feeder, NoeudSig.station, NoeudSig.categorie, NoeudSig.feeder_id
            ),
        )
        .where(SchemaUnifilairePoste.schema_id == schema_id)
        .order_by(SchemaUnifilairePoste.rang)
    )
    return list(result.unique().scalars().all())


async def poste(db: AsyncSession, schema_id: int, poste_schema_id: int) -> SchemaUnifilairePoste | None:
    return await db.scalar(
        select(SchemaUnifilairePoste).where(
            SchemaUnifilairePoste.schema_id == schema_id, SchemaUnifilairePoste.id == poste_schema_id
        )
    )


async def noeuds_sig_nommes(db: AsyncSession) -> list[tuple[int, str]]:
    rows = (await db.execute(select(NoeudSig.id, NoeudSig.nom).where(NoeudSig.nom.isnot(None)))).all()
    return [(int(i), str(n)) for i, n in rows]


async def get_noeud_sig(db: AsyncSession, noeud_id: int) -> NoeudSig | None:
    return await db.get(NoeudSig, noeud_id)


async def rechercher_noeuds_sig(db: AsyncSession, recherche: str, *, limite: int = 20) -> list[NoeudSig]:
    motif = f"%{recherche.strip()}%"
    result = await db.execute(
        select(NoeudSig)
        .options(
            load_only(NoeudSig.id, NoeudSig.nom, NoeudSig.nom_feeder, NoeudSig.station, NoeudSig.categorie)
        )
        .where(or_(NoeudSig.nom.ilike(motif), NoeudSig.nom_feeder.ilike(motif)))
        .order_by(NoeudSig.nom, NoeudSig.id)
        .limit(limite)
    )
    return list(result.scalars().all())


async def enregistrer_sig_auto(db: AsyncSession, valeurs: list[dict[str, object]]) -> None:
    """Rapprochement SIG automatique : [{"i": id, "n": noeud_sig_id|None, "r": statut|None}]."""
    if not valeurs:
        return
    stmt = (
        update(SchemaUnifilairePoste.__table__)
        .where(SchemaUnifilairePoste.__table__.c.id == bindparam("i"))
        .values(noeud_sig_id=bindparam("n"), rapprochement_sig=bindparam("r"))
    )
    await db.execute(stmt, valeurs)


async def lier_sig(db: AsyncSession, poste_schema_id: int, noeud_id: int | None, rapprochement: str | None) -> None:
    await db.execute(
        update(SchemaUnifilairePoste)
        .where(SchemaUnifilairePoste.id == poste_schema_id)
        .values(noeud_sig_id=noeud_id, rapprochement_sig=rapprochement)
    )


async def definir_statut_sir(db: AsyncSession, poste_schema_ids: list[int], statut: str | None) -> None:
    if poste_schema_ids:
        await db.execute(
            update(SchemaUnifilairePoste)
            .where(SchemaUnifilairePoste.id.in_(poste_schema_ids))
            .values(statut_sir=statut)
        )


async def relier_sir(db: AsyncSession, poste_schema_ids: list[int], poste_id: int) -> None:
    """Postes du schéma reliés au poste créé : association manuelle, plus de décision « à créer »."""
    if poste_schema_ids:
        await db.execute(
            update(SchemaUnifilairePoste)
            .where(SchemaUnifilairePoste.id.in_(poste_schema_ids))
            .values(poste_id=poste_id, rapprochement="manuel", statut_sir=None)
        )


async def postes_a_creer_non_relies(db: AsyncSession) -> list[tuple[int, str | None]]:
    """Postes de tous les schémas marqués « à créer » et pas encore reliés : (id, libellé)."""
    rows = (
        await db.execute(
            select(SchemaUnifilairePoste.id, SchemaUnifilairePoste.libelle).where(
                SchemaUnifilairePoste.statut_sir == "a_creer", SchemaUnifilairePoste.poste_id.is_(None)
            )
        )
    ).all()
    return [(int(i), lib) for i, lib in rows]


# ── Postes à créer ──────────────────────────────────────────────────────────────


def _options_demande():  # noqa: ANN202
    return (
        joinedload(PosteACreer.poste_source),
        joinedload(PosteACreer.feeder),
        joinedload(PosteACreer.noeud_sig).load_only(NoeudSig.id, NoeudSig.nom),
        joinedload(PosteACreer.propose_par),
        joinedload(PosteACreer.traite_par),
    )


async def creer_demande(db: AsyncSession, **valeurs: object) -> PosteACreer:
    demande = PosteACreer(**valeurs)
    db.add(demande)
    await db.flush()
    return demande


async def demande(db: AsyncSession, demande_id: int) -> PosteACreer | None:
    result = await db.execute(select(PosteACreer).options(*_options_demande()).where(PosteACreer.id == demande_id))
    return result.unique().scalar_one_or_none()


async def lister_demandes(
    db: AsyncSession, *, statut: str | None, page: int, page_size: int
) -> tuple[list[PosteACreer], int]:
    filtre = [PosteACreer.statut == statut] if statut else []
    total = await db.scalar(select(func.count(PosteACreer.id)).where(*filtre))
    result = await db.execute(
        select(PosteACreer)
        .options(*_options_demande())
        .where(*filtre)
        .order_by(PosteACreer.propose_le.desc(), PosteACreer.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.unique().scalars().all()), int(total or 0)


async def demandes_en_attente_par_poste_schema(db: AsyncSession, poste_schema_ids: list[int]) -> dict[int, int]:
    if not poste_schema_ids:
        return {}
    rows = (
        await db.execute(
            select(PosteACreer.schema_poste_id, PosteACreer.id).where(
                PosteACreer.statut == "propose", PosteACreer.schema_poste_id.in_(poste_schema_ids)
            )
        )
    ).all()
    return {int(s): int(i) for s, i in rows if s is not None}


async def demandes_en_attente_du_feeder(db: AsyncSession, feeder_id: int) -> list[PosteACreer]:
    result = await db.execute(
        select(PosteACreer)
        .options(load_only(PosteACreer.id, PosteACreer.libelle))
        .where(PosteACreer.statut == "propose", PosteACreer.feeder_id == feeder_id)
    )
    return list(result.scalars().all())


async def traiter_demande(
    db: AsyncSession, demande_id: int, *, statut: str, user_id: int, poste_id: int | None, motif: str | None
) -> None:
    await db.execute(
        update(PosteACreer)
        .where(PosteACreer.id == demande_id)
        .values(statut=statut, traite_par_id=user_id, traite_le=datetime.now(), poste_id=poste_id, motif_rejet=motif)
    )


async def code_poste_existe(db: AsyncSession, code: str) -> bool:
    return (await db.scalar(select(func.count(Poste.id)).where(Poste.code == code))) > 0


async def schema_nom(db: AsyncSession, schema_id: int) -> str | None:
    return await db.scalar(select(SchemaUnifilaire.nom).where(SchemaUnifilaire.id == schema_id))
