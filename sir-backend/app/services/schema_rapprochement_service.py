"""Rapprochement Schéma unifilaire / SIG / SIR et postes à créer dans SIR.

Écran demandé par le chef de service (suggestion du 23/11/2026) : pour chaque poste du schéma,
le nœud SIG (recherche) et le poste SIR (relier, « Inactif » ou « À créer »). « À créer » passe par une
recherche assistée (poste source, feeder, poste) et alimente la liste des postes à créer, que l'Admin SCR
valide (le poste est créé dans SIR et relié au schéma) ou rejette.

Droits : rapprochement et propositions = Admin SCR, BCC, BRC ; validation / rejet = Admin SCR.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.schema_unifilaire import PosteACreer, SchemaUnifilairePoste
from app.models.utilisateurs import Utilisateur
from app.repositories import reseau_distribution_repository as reseau_repo
from app.repositories import schema_rapprochement_repository as repo
from app.repositories import schema_unifilaire_repository as schema_repo
from app.schemas.common import PaginatedResponse
from app.schemas.schema_unifilaire import (
    CompteursRapprochementResponse,
    LigneRapprochementResponse,
    NoeudSigCourtResponse,
    PosteACreerResponse,
    PosteSirCourtResponse,
    RapprochementSigResponse,
    SuggestionCreationResponse,
)
from app.services import schema_unifilaire_service as schema_svc
from app.services.schema_unifilaire_graphe import postes_voisins
from app.services.schema_unifilaire_rapprochement import cle_poste, rapprocher
from app.utils.audit import ACTION_CREATE, ACTION_UPDATE, log_audit

ROLES_RAPPROCHEMENT = {"ADMIN_SCR", "BCC", "BRC"}
ROLES_VALIDATION = {"ADMIN_SCR"}
FILTRES = {"tous", "a_traiter", "sig_manquant", "sir_relies", "ambigus", "a_creer", "inactifs"}


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _roles(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _verifier(user: Utilisateur, roles: set[str], message: str) -> None:
    if not is_superadmin(user) and not _roles(user) & roles:
        raise _erreur(status.HTTP_403_FORBIDDEN, message)


def peut_rapprocher(user: Utilisateur) -> bool:
    return is_superadmin(user) or bool(_roles(user) & ROLES_RAPPROCHEMENT)


def peut_valider(user: Utilisateur) -> bool:
    return is_superadmin(user) or bool(_roles(user) & ROLES_VALIDATION)


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


# ── Lecture ─────────────────────────────────────────────────────────────────────


def _ligne(p: SchemaUnifilairePoste, demande_id: int | None) -> LigneRapprochementResponse:
    noeud = p.__dict__.get("noeud_sig")
    poste = p.__dict__.get("poste")
    feeder = poste.__dict__.get("feeder") if poste is not None else None
    poste_source = feeder.__dict__.get("poste_source") if feeder is not None else None
    return LigneRapprochementResponse(
        id=p.id,
        rang=p.rang,
        libelle=p.libelle,
        sig=NoeudSigCourtResponse(
            id=noeud.id, nom=noeud.nom, nom_feeder=noeud.nom_feeder, station=noeud.station, categorie=noeud.categorie
        )
        if noeud is not None
        else None,
        rapprochement_sig=p.rapprochement_sig,
        sir=PosteSirCourtResponse(
            id=poste.id,
            code=poste.code,
            libelle=poste.libelle,
            feeder_libelle=feeder.libelle if feeder is not None else None,
            poste_source_libelle=poste_source.libelle if poste_source is not None else None,
        )
        if poste is not None
        else None,
        rapprochement=p.rapprochement,
        statut_sir=p.statut_sir,
        demande_id=demande_id,
    )


def _a_traiter(p: SchemaUnifilairePoste) -> bool:
    return bool(p.libelle) and p.poste_id is None and p.statut_sir is None


def _garder(p: SchemaUnifilairePoste, filtre: str) -> bool:
    if filtre == "a_traiter":
        return _a_traiter(p)
    if filtre == "sig_manquant":
        return bool(p.libelle) and p.noeud_sig_id is None
    if filtre == "sir_relies":
        return p.poste_id is not None
    if filtre == "ambigus":
        return p.poste_id is None and (p.rapprochement == "ambigu" or p.rapprochement_sig == "ambigu")
    if filtre == "a_creer":
        return p.statut_sir == "a_creer"
    if filtre == "inactifs":
        return p.statut_sir == "inactif"
    return True


def compter(liste: list[SchemaUnifilairePoste]) -> CompteursRapprochementResponse:
    return CompteursRapprochementResponse(
        total=len(liste),
        sans_nom=sum(1 for p in liste if not p.libelle),
        sig_relies=sum(1 for p in liste if p.noeud_sig_id is not None),
        sig_ambigus=sum(1 for p in liste if p.noeud_sig_id is None and p.rapprochement_sig == "ambigu"),
        sir_relies=sum(1 for p in liste if p.poste_id is not None),
        sir_ambigus=sum(1 for p in liste if p.poste_id is None and p.rapprochement == "ambigu"),
        a_creer=sum(1 for p in liste if p.statut_sir == "a_creer"),
        inactifs=sum(1 for p in liste if p.statut_sir == "inactif"),
        a_traiter=sum(1 for p in liste if _a_traiter(p)),
    )


async def lignes(
    db: AsyncSession, schema_id: int, *, filtre: str, recherche: str | None, page: int, page_size: int
) -> PaginatedResponse[LigneRapprochementResponse]:
    await schema_svc.obtenir(db, schema_id)
    liste = [p for p in await repo.postes(db, schema_id) if _garder(p, filtre if filtre in FILTRES else "tous")]
    if recherche and recherche.strip():
        q = _sans_accents(recherche.strip())
        liste = [
            p
            for p in liste
            if q in _sans_accents(p.libelle or "")
            or (p.__dict__.get("poste") is not None and q in _sans_accents(p.poste.libelle))
            or (p.__dict__.get("noeud_sig") is not None and q in _sans_accents(p.noeud_sig.nom or ""))
        ]
    total = len(liste)
    page_items = liste[(page - 1) * page_size : page * page_size]
    demandes = await repo.demandes_en_attente_par_poste_schema(db, [p.id for p in page_items])
    return PaginatedResponse(
        items=[_ligne(p, demandes.get(p.id)) for p in page_items], total=total, page=page, page_size=page_size
    )


async def compteurs(db: AsyncSession, schema_id: int) -> CompteursRapprochementResponse:
    await schema_svc.obtenir(db, schema_id)
    return compter(await repo.postes(db, schema_id))


async def rechercher_sig(db: AsyncSession, recherche: str) -> list[NoeudSigCourtResponse]:
    if len(recherche.strip()) < 2:
        return []
    return [
        NoeudSigCourtResponse(id=n.id, nom=n.nom, nom_feeder=n.nom_feeder, station=n.station, categorie=n.categorie)
        for n in await repo.rechercher_noeuds_sig(db, recherche)
    ]


# ── Rapprochement ───────────────────────────────────────────────────────────────


async def rapprocher_sig(db: AsyncSession, schema_id: int, user: Utilisateur) -> RapprochementSigResponse:
    """Nœud SIG de même nom pour chaque poste du schéma (les choix manuels sont gardés)."""
    _verifier(user, ROLES_RAPPROCHEMENT, "Réservé à l'Admin SCR, au BCC et au BRC")
    await schema_svc.obtenir(db, schema_id)
    liste = [p for p in await repo.postes(db, schema_id) if p.rapprochement_sig != "manuel"]
    noeuds = await repo.noeuds_sig_nommes(db)
    resultats = rapprocher([p.libelle for p in liste], [(i, nom, None) for i, nom in noeuds])
    nommes = [bool(p.libelle) for p in liste]
    await repo.enregistrer_sig_auto(db, [{"i": p.id, "n": nid, "r": st} for p, (nid, st) in zip(liste, resultats)])
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="schema_unifilaire_postes",
        record_id=schema_id,
        new_values={"rapprochement_sig": "auto", "schema_id": schema_id},
    )
    await db.commit()
    return RapprochementSigResponse(
        relies=sum(1 for nid, _ in resultats if nid),
        ambigus=sum(1 for _, st in resultats if st == "ambigu"),
        non_trouves=sum(1 for nomme, (nid, st) in zip(nommes, resultats) if nomme and not nid and st != "ambigu"),
    )


async def _poste_schema(db: AsyncSession, schema_id: int, poste_schema_id: int) -> SchemaUnifilairePoste:
    await schema_svc.obtenir(db, schema_id)
    p = await repo.poste(db, schema_id, poste_schema_id)
    if p is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Poste introuvable sur ce schéma")
    return p


async def _ligne_fraiche(db: AsyncSession, schema_id: int, poste_schema_id: int) -> LigneRapprochementResponse:
    db.expire_all()
    p = next(x for x in await repo.postes(db, schema_id) if x.id == poste_schema_id)
    demandes = await repo.demandes_en_attente_par_poste_schema(db, [p.id])
    return _ligne(p, demandes.get(p.id))


async def lier_sig(
    db: AsyncSession, schema_id: int, poste_schema_id: int, noeud_id: int | None, user: Utilisateur
) -> LigneRapprochementResponse:
    _verifier(user, ROLES_RAPPROCHEMENT, "Réservé à l'Admin SCR, au BCC et au BRC")
    p = await _poste_schema(db, schema_id, poste_schema_id)
    if noeud_id is not None and await repo.get_noeud_sig(db, noeud_id) is None:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Nœud SIG {noeud_id} introuvable")
    ancien = p.noeud_sig_id
    # Délier à la main : « manuel » sans nœud, pour que le rapprochement automatique ne le remette pas
    await repo.lier_sig(db, p.id, noeud_id, "manuel")
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="schema_unifilaire_postes",
        record_id=p.id,
        old_values={"noeud_sig_id": ancien},
        new_values={"noeud_sig_id": noeud_id},
    )
    p_id = p.id
    await db.commit()
    return await _ligne_fraiche(db, schema_id, p_id)


async def lier_sir(
    db: AsyncSession, schema_id: int, poste_schema_id: int, poste_id: int | None, user: Utilisateur
) -> LigneRapprochementResponse:
    """Relie le poste du schéma à un poste SIR existant (ou le délie) ; annule « Inactif »."""
    _verifier(user, ROLES_RAPPROCHEMENT, "Réservé à l'Admin SCR, au BCC et au BRC")
    p = await _poste_schema(db, schema_id, poste_schema_id)
    if poste_id is not None:
        poste = await reseau_repo.get_poste(db, poste_id)
        if poste is None or not poste.is_active:
            raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Poste SIR {poste_id} introuvable ou inactif")
    ancien = p.poste_id
    await schema_repo.associer(db, p.id, poste_id, "manuel" if poste_id is not None else None)
    if poste_id is not None and p.statut_sir == "inactif":
        await repo.definir_statut_sir(db, [p.id], None)
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="schema_unifilaire_postes",
        record_id=p.id,
        old_values={"poste_id": ancien},
        new_values={"poste_id": poste_id},
    )
    p_id = p.id
    await db.commit()
    return await _ligne_fraiche(db, schema_id, p_id)


async def definir_statut_sir(
    db: AsyncSession, schema_id: int, poste_schema_id: int, statut: str | None, user: Utilisateur
) -> LigneRapprochementResponse:
    """« Inactif » : poste hors service, ni relié ni à créer dans SIR."""
    _verifier(user, ROLES_RAPPROCHEMENT, "Réservé à l'Admin SCR, au BCC et au BRC")
    p = await _poste_schema(db, schema_id, poste_schema_id)
    if p.statut_sir == "a_creer":
        raise _erreur(status.HTTP_409_CONFLICT, "Une création est proposée pour ce poste : rejetez-la d'abord")
    if statut == "inactif" and p.poste_id is not None:
        await schema_repo.associer(db, p.id, None, None)
    await repo.definir_statut_sir(db, [p.id], statut)
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="schema_unifilaire_postes",
        record_id=p.id,
        old_values={"statut_sir": p.statut_sir, "poste_id": p.poste_id},
        new_values={"statut_sir": statut},
    )
    p_id = p.id
    await db.commit()
    return await _ligne_fraiche(db, schema_id, p_id)


async def suggestion_creation(db: AsyncSession, schema_id: int, poste_schema_id: int) -> SuggestionCreationResponse:
    """Recherche assistée : feeder du nœud SIG rapproché, sinon le plus fréquent chez les postes voisins."""
    schema = await schema_repo.obtenir(db, schema_id)
    p = await _poste_schema(db, schema_id, poste_schema_id)
    libelle = re.sub(r"\s+", " ", (p.libelle or "").strip())
    feeder_id: int | None = None
    origine: str | None = None
    if p.noeud_sig_id is not None:
        noeud = await repo.get_noeud_sig(db, p.noeud_sig_id)
        if noeud is not None and noeud.feeder_id is not None:
            feeder_id, origine = noeud.feeder_id, "sig"
    if feeder_id is None and schema is not None:
        graphe = await schema_svc._graphe(db, schema)  # noqa: SLF001 — cache des graphes du service
        rangs = set(postes_voisins(graphe, p.rang))
        voisins = [x for x in await repo.postes(db, schema_id) if x.rang in rangs and x.__dict__.get("poste")]
        frequents = Counter(x.poste.feeder_id for x in voisins if x.poste.feeder_id).most_common(1)
        if frequents:
            feeder_id, origine = frequents[0][0], "voisins"
    feeder = await reseau_repo.get_feeder(db, feeder_id) if feeder_id else None
    return SuggestionCreationResponse(
        libelle=libelle,
        poste_source_id=feeder.poste_source_id if feeder is not None else None,
        poste_source_libelle=feeder.poste_source.libelle if feeder is not None and feeder.poste_source else None,
        feeder_id=feeder.id if feeder is not None else None,
        feeder_libelle=feeder.libelle if feeder is not None else None,
        origine=origine if feeder is not None else None,
    )


# ── Postes à créer ──────────────────────────────────────────────────────────────


def _nom_utilisateur(u: Utilisateur | None) -> str | None:
    return f"{u.prenom} {u.nom}" if u is not None else None


def _demande_response(d: PosteACreer) -> PosteACreerResponse:
    noeud = d.__dict__.get("noeud_sig")
    return PosteACreerResponse(
        id=d.id,
        schema_nom=d.schema_nom,
        libelle_schema=d.libelle_schema,
        libelle=d.libelle,
        poste_source_id=d.poste_source_id,
        poste_source_libelle=d.poste_source.libelle if d.poste_source is not None else None,
        feeder_id=d.feeder_id,
        feeder_libelle=d.feeder.libelle if d.feeder is not None else None,
        noeud_sig_nom=noeud.nom if noeud is not None else None,
        statut=d.statut,
        motif_rejet=d.motif_rejet,
        poste_id=d.poste_id,
        poste_code=None,
        propose_par=_nom_utilisateur(d.propose_par),
        propose_le=d.propose_le,
        traite_par=_nom_utilisateur(d.traite_par),
        traite_le=d.traite_le,
    )


async def proposer(
    db: AsyncSession, schema_id: int, poste_schema_id: int, libelle: str, feeder_id: int, user: Utilisateur
) -> PosteACreerResponse:
    _verifier(user, ROLES_RAPPROCHEMENT, "Réservé à l'Admin SCR, au BCC et au BRC")
    p = await _poste_schema(db, schema_id, poste_schema_id)
    if p.poste_id is not None:
        raise _erreur(status.HTTP_409_CONFLICT, "Ce poste du schéma est déjà relié à un poste SIR")
    if p.statut_sir == "a_creer":
        raise _erreur(status.HTTP_409_CONFLICT, "Une création est déjà proposée pour ce poste")
    feeder = await reseau_repo.get_feeder(db, feeder_id)
    if feeder is None or not feeder.is_active:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Feeder {feeder_id} introuvable ou inactif")
    libelle = re.sub(r"\s+", " ", libelle.strip())
    cle = cle_poste(libelle)
    for autre in await repo.demandes_en_attente_du_feeder(db, feeder.id):
        if cle_poste(autre.libelle) == cle:
            raise _erreur(status.HTTP_409_CONFLICT, f"« {autre.libelle} » est déjà proposé sur ce feeder")
    demande = await repo.creer_demande(
        db,
        schema_poste_id=p.id,
        schema_nom=await repo.schema_nom(db, schema_id),
        libelle_schema=p.libelle,
        libelle=libelle,
        poste_source_id=feeder.poste_source_id,
        feeder_id=feeder.id,
        noeud_sig_id=p.noeud_sig_id,
        statut="propose",
        propose_par_id=user.id,
    )
    await repo.definir_statut_sir(db, [p.id], "a_creer")
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_CREATE,
        table_name="postes_a_creer",
        record_id=demande.id,
        new_values={"libelle": libelle, "feeder_id": feeder.id, "schema_poste_id": p.id},
    )
    demande_id = demande.id
    await db.commit()
    rechargee = await repo.demande(db, demande_id)
    assert rechargee is not None
    return _demande_response(rechargee)


async def lister_demandes(
    db: AsyncSession, statut: str | None, page: int, page_size: int
) -> PaginatedResponse[PosteACreerResponse]:
    items, total = await repo.lister_demandes(db, statut=statut, page=page, page_size=page_size)
    return PaginatedResponse(items=[_demande_response(d) for d in items], total=total, page=page, page_size=page_size)


async def _demande_en_attente(db: AsyncSession, demande_id: int) -> PosteACreer:
    d = await repo.demande(db, demande_id)
    if d is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, f"Proposition {demande_id} introuvable")
    if d.statut != "propose":
        raise _erreur(status.HTTP_409_CONFLICT, "Cette proposition a déjà été traitée")
    return d


async def _code_libre(db: AsyncSession, demande_id: int) -> str:
    for suffixe in ("", "A", "B", "C", "D"):
        code = f"SU{demande_id:06d}{suffixe}"
        if not await repo.code_poste_existe(db, code):
            return code
    raise _erreur(status.HTTP_409_CONFLICT, "Code poste indisponible : saisissez un code")


async def valider(db: AsyncSession, demande_id: int, code: str | None, user: Utilisateur) -> PosteACreerResponse:
    """Crée le poste dans SIR (feeder et service du feeder) et le relie aux postes des schémas."""
    _verifier(user, ROLES_VALIDATION, "Validation réservée à l'Admin SCR")
    d = await _demande_en_attente(db, demande_id)
    feeder = await reseau_repo.get_feeder(db, d.feeder_id)
    if feeder is None or not feeder.is_active:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Le feeder de la proposition n'est plus actif")
    code = (code or "").strip() or await _code_libre(db, d.id)
    if await repo.code_poste_existe(db, code):
        raise _erreur(status.HTTP_409_CONFLICT, f"Le code poste {code} existe déjà")
    poste = await reseau_repo.create_poste(
        db, code=code, libelle=d.libelle, feeder_id=feeder.id, service_id=feeder.service_id
    )
    # Postes des schémas à relier : celui de la proposition, et ceux du même nom marqués « à créer »
    # (le schéma a pu être réimporté depuis la proposition)
    cles = {cle_poste(d.libelle_schema), cle_poste(d.libelle)} - {""}
    a_relier = {i for i, lib in await repo.postes_a_creer_non_relies(db) if cle_poste(lib) in cles}
    if d.schema_poste_id is not None:
        a_relier.add(d.schema_poste_id)
    await repo.relier_sir(db, sorted(a_relier), poste.id)
    await repo.traiter_demande(db, d.id, statut="valide", user_id=user.id, poste_id=poste.id, motif=None)
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_CREATE,
        table_name="postes",
        record_id=poste.id,
        new_values={"code": code, "libelle": d.libelle, "feeder_id": feeder.id, "postes_a_creer_id": d.id},
    )
    d_id = d.id
    await db.commit()
    db.expire_all()
    rechargee = await repo.demande(db, d_id)
    assert rechargee is not None
    reponse = _demande_response(rechargee)
    reponse.poste_code = code
    return reponse


async def rejeter(db: AsyncSession, demande_id: int, motif: str, user: Utilisateur) -> PosteACreerResponse:
    _verifier(user, ROLES_VALIDATION, "Rejet réservé à l'Admin SCR")
    d = await _demande_en_attente(db, demande_id)
    await repo.traiter_demande(db, d.id, statut="rejete", user_id=user.id, poste_id=None, motif=motif.strip())
    if d.schema_poste_id is not None:
        await repo.definir_statut_sir(db, [d.schema_poste_id], None)
    await log_audit(
        db,
        user_id=user.id,
        action=ACTION_UPDATE,
        table_name="postes_a_creer",
        record_id=d.id,
        old_values={"statut": "propose"},
        new_values={"statut": "rejete", "motif_rejet": motif.strip()},
    )
    d_id = d.id
    await db.commit()
    db.expire_all()
    rechargee = await repo.demande(db, d_id)
    assert rechargee is not None
    return _demande_response(rechargee)
