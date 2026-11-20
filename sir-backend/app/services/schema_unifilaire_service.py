"""Schémas unifilaires : consultation, postes cliquables, postes entre deux postes, association."""

from __future__ import annotations

import gzip
import json
from collections import OrderedDict

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.schema_unifilaire import SchemaUnifilaire, SchemaUnifilairePoste
from app.models.utilisateurs import Utilisateur
from app.repositories import reseau_distribution_repository as reseau_repo
from app.repositories import schema_unifilaire_repository as repo
from app.schemas.schema_unifilaire import (
    DerivationResponse,
    PosteSchemaResponse,
    PostesEntreResponse,
    SchemaUnifilaireResponse,
)
from app.services.schema_unifilaire_graphe import Graphe, postes_entre
from app.utils.audit import ACTION_UPDATE, log_audit

# Graphes décodés gardés en mémoire (quelques centaines de Ko chacun) : un schéma ne change qu'à l'import
_CACHE_GRAPHES: OrderedDict[tuple[int, str], Graphe] = OrderedDict()
_CACHE_MAX = 6
ROLES_ASSOCIATION = {"ADMIN_SCR"}


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _schema_response(s: SchemaUnifilaire) -> SchemaUnifilaireResponse:
    return SchemaUnifilaireResponse(
        id=s.id,
        nom=s.nom,
        fichier=s.fichier,
        region_id=s.region_id,
        region_libelle=s.region.libelle if s.region is not None else None,
        largeur=s.largeur,
        hauteur=s.hauteur,
        zoom_max=s.zoom_max,
        nb_postes=s.nb_postes,
        importe_le=s.importe_le,
    )


def _poste_response(p: SchemaUnifilairePoste) -> PosteSchemaResponse:
    poste = p.__dict__.get("poste")
    return PosteSchemaResponse(
        id=p.id,
        rang=p.rang,
        libelle=p.libelle,
        forme=p.forme,
        puissance_kva=p.puissance_kva,
        x0=p.x0,
        y0=p.y0,
        x1=p.x1,
        y1=p.y1,
        lx0=p.lx0,
        ly0=p.ly0,
        lx1=p.lx1,
        ly1=p.ly1,
        poste_id=p.poste_id,
        poste_code=poste.code if poste is not None else None,
        poste_libelle=poste.libelle if poste is not None else None,
        rapprochement=p.rapprochement,
    )


async def lister(db: AsyncSession) -> list[SchemaUnifilaireResponse]:
    return [_schema_response(s) for s in await repo.lister(db)]


async def _schema(db: AsyncSession, schema_id: int) -> SchemaUnifilaire:
    schema = await repo.obtenir(db, schema_id)
    if schema is None or not schema.is_active:
        raise _erreur(status.HTTP_404_NOT_FOUND, f"Schéma unifilaire {schema_id} introuvable")
    return schema


async def obtenir(db: AsyncSession, schema_id: int) -> SchemaUnifilaireResponse:
    return _schema_response(await _schema(db, schema_id))


async def postes(db: AsyncSession, schema_id: int) -> list[PosteSchemaResponse]:
    await _schema(db, schema_id)
    return [_poste_response(p) for p in await repo.postes(db, schema_id)]


async def tuile(db: AsyncSession, schema_id: int, z: int, x: int, y: int) -> bytes | None:
    """Tuile PNG ; None = zone blanche (non enregistrée à l'import)."""
    return await repo.tuile(db, schema_id, z, x, y)


async def _graphe(db: AsyncSession, schema: SchemaUnifilaire) -> Graphe:
    cle = (schema.id, schema.importe_le.isoformat())
    if cle in _CACHE_GRAPHES:
        _CACHE_GRAPHES.move_to_end(cle)
        return _CACHE_GRAPHES[cle]
    brut = await repo.graphe(db, schema.id)
    if not brut:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Graphe du schéma absent : réimportez le schéma")
    graphe = Graphe.depuis_json(json.loads(gzip.decompress(brut)))
    _CACHE_GRAPHES[cle] = graphe
    while len(_CACHE_GRAPHES) > _CACHE_MAX:
        _CACHE_GRAPHES.popitem(last=False)
    return graphe


async def entre(db: AsyncSession, schema_id: int, debut_id: int, fin_id: int) -> PostesEntreResponse:
    """Postes situés entre deux postes du schéma, le long des lignes dessinées."""
    schema = await _schema(db, schema_id)
    liste = await repo.postes(db, schema_id)
    par_id = {p.id: p for p in liste}
    par_rang = {p.rang: p for p in liste}
    if debut_id not in par_id or fin_id not in par_id:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Poste introuvable sur ce schéma")
    graphe = await _graphe(db, schema)
    resultat = postes_entre(graphe, par_id[debut_id].rang, par_id[fin_id].rang)
    if resultat is None:
        raise _erreur(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Aucune ligne du schéma ne relie ces deux postes : choisissez deux postes du même départ",
        )

    def reponses(rangs: list[int]) -> list[PosteSchemaResponse]:
        return [_poste_response(par_rang[r]) for r in rangs if r in par_rang]

    return PostesEntreResponse(
        chemin=reponses(resultat.rangs_chemin),
        antennes=reponses(resultat.rangs_antennes),
        derivations=[
            DerivationResponse(
                depuis_id=par_rang[d.depuis_rang].id if d.depuis_rang in par_rang else None,
                postes=reponses(d.rangs),
            )
            for d in resultat.derivations
        ],
        postes_hors_limite=resultat.postes_hors_limite,
        trace=[(round(x, 1), round(y, 1)) for x, y in resultat.trace],
    )


async def associer(
    db: AsyncSession, schema_id: int, poste_schema_id: int, poste_id: int | None, user: Utilisateur
) -> PosteSchemaResponse:
    """Relie (ou délie) un poste du schéma à un poste SIRV2 ; repris aux imports suivants."""
    if not is_superadmin(user) and not {ur.role.nom for ur in user.user_roles} & ROLES_ASSOCIATION:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Réservé à l'Admin SCR")
    await _schema(db, schema_id)
    poste_schema = await repo.poste(db, schema_id, poste_schema_id)
    if poste_schema is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Poste introuvable sur ce schéma")
    if poste_id is not None:
        poste = await reseau_repo.get_poste(db, poste_id)
        if poste is None or not poste.is_active:
            raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Poste SIRV2 {poste_id} introuvable ou inactif")
    ancien = poste_schema.poste_id
    await repo.associer(db, poste_schema_id, poste_id, "manuel" if poste_id is not None else None)
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="schema_unifilaire_postes",
        record_id=poste_schema_id,
        old_values={"poste_id": ancien},
        new_values={"poste_id": poste_id},
    )
    await db.commit()
    rafraichi = next(p for p in await repo.postes(db, schema_id) if p.id == poste_schema_id)
    return _poste_response(rafraichi)
