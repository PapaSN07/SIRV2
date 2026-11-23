"""Rapprochement Schéma / SIG / SIR et postes à créer (SQLite + requêtes SQL Server)."""

from __future__ import annotations

import gzip
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.geo import Agence, Region, Service
from app.models.reseau import Feeder, Poste, PosteSource
from app.models.schema_unifilaire import PosteACreer, SchemaUnifilaire, SchemaUnifilairePoste
from app.models.sig import NoeudSig
from app.models.utilisateurs import Utilisateur
from app.services import schema_rapprochement_service as svc
from app.services.schema_unifilaire_graphe import Graphe, postes_voisins


def _role(nom: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, prenom="Awa", nom="Diop", user_roles=[SimpleNamespace(role=SimpleNamespace(nom=nom))])


ADMIN_SCR, BCC, BRC_LECTURE = _role("ADMIN_SCR"), _role("BCC"), _role("ADMIN_SAQS")

# Ligne : P0 (relié, feeder 10) - P1 (à créer) - P2 (relié, feeder 10) ; P3 isolé
GRAPHE = {"coords": [[0, 0], [10, 0], [20, 0], [90, 90]], "aretes": [[0, 1, 10], [1, 2, 10]], "postes": [0, 1, 2, 3]}


@pytest.fixture
async def db():
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(moteur.sync_engine, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-23"))
    async with moteur.begin() as conn:
        for modele in (Region, Agence, Service, PosteSource, Feeder, Poste, NoeudSig, Utilisateur, SchemaUnifilaire, SchemaUnifilairePoste, PosteACreer):
            await conn.run_sync(modele.__table__.create)
    async with AsyncSession(moteur) as session:
        session.add_all([
            PosteSource(id=1, code="HANN", libelle="HANN", is_active=True),
            Feeder(id=10, code="F10", libelle="OUAKAM", poste_source_id=1, service_id=5, is_active=True),
            Poste(id=100, code="P100", libelle="Ngor Village", feeder_id=10, is_active=True),
            Poste(id=101, code="P101", libelle="Almadies 2", feeder_id=10, is_active=True),
            NoeudSig(id=7, legacy_id=7, legacy_fid=7, nom="SORAGUIN", nom_feeder="OUAKAM", feeder_id=10, station="HANN"),
            NoeudSig(id=8, legacy_id=8, legacy_fid=8, nom="MAMELLES", nom_feeder="X", station="HANN"),
            NoeudSig(id=9, legacy_id=9, legacy_fid=9, nom="MAMELLES", nom_feeder="Y", station="HANN"),
            SchemaUnifilaire(id=1, nom="Dakar (BCC)", fichier="d.pdf", largeur=100, hauteur=100, zoom_max=3,
                             graphe=gzip.compress(json.dumps(GRAPHE).encode()), nb_postes=4, is_active=True),
            SchemaUnifilairePoste(id=1, schema_id=1, rang=0, libelle="Ngor Village", forme="carre", x0=0, y0=0, x1=1, y1=1,
                                  poste_id=100, rapprochement="auto"),
            SchemaUnifilairePoste(id=2, schema_id=1, rang=1, libelle="Poste HTA Soraguin", forme="carre", x0=0, y0=0, x1=1, y1=1),
            SchemaUnifilairePoste(id=3, schema_id=1, rang=2, libelle="Almadies 2", forme="carre", x0=0, y0=0, x1=1, y1=1,
                                  poste_id=101, rapprochement="auto"),
            SchemaUnifilairePoste(id=4, schema_id=1, rang=3, libelle="Mamelles", forme="rond", x0=0, y0=0, x1=1, y1=1),
        ])
        await session.commit()
        yield session
    await moteur.dispose()


@pytest.fixture(autouse=True)
def _sans_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "log_audit", AsyncMock())


def test_postes_voisins_le_long_des_lignes() -> None:
    g = Graphe.depuis_json(GRAPHE)
    assert postes_voisins(g, 1) == [0, 2]
    assert postes_voisins(g, 3) == []


async def test_rapprochement_sig_par_le_nom(db: AsyncSession) -> None:
    r = await svc.rapprocher_sig(db, 1, ADMIN_SCR)  # type: ignore[arg-type]
    assert (r.relies, r.ambigus) == (1, 1)  # SORAGUIN relié ; MAMELLES porté par deux nœuds
    c = await svc.compteurs(db, 1)
    assert (c.sig_relies, c.sig_ambigus, c.sir_relies, c.a_traiter) == (1, 1, 2, 2)
    page = await svc.lignes(db, 1, filtre="a_traiter", recherche=None, page=1, page_size=50)
    assert [l.libelle for l in page.items] == ["Poste HTA Soraguin", "Mamelles"]
    assert page.items[0].sig is not None and page.items[0].sig.nom == "SORAGUIN"


async def test_suggestion_feeder_du_sig_puis_des_voisins(db: AsyncSession) -> None:
    s = await svc.suggestion_creation(db, 1, 2)
    assert (s.feeder_id, s.origine) == (10, "voisins")
    await svc.rapprocher_sig(db, 1, ADMIN_SCR)  # type: ignore[arg-type]
    s = await svc.suggestion_creation(db, 1, 2)
    assert (s.feeder_id, s.poste_source_id, s.origine) == (10, 1, "sig")


async def test_proposer_valider_cree_le_poste_et_le_relie(db: AsyncSession) -> None:
    d = await svc.proposer(db, 1, 2, "Soraguin", 10, BCC)  # type: ignore[arg-type]
    assert (d.statut, d.poste_source_id, d.feeder_libelle) == ("propose", 1, "OUAKAM")
    with pytest.raises(HTTPException) as doublon:
        await svc.proposer(db, 1, 2, "Soraguin", 10, BCC)  # type: ignore[arg-type]
    assert doublon.value.status_code == 409
    with pytest.raises(HTTPException) as interdit:
        await svc.valider(db, d.id, None, BCC)  # type: ignore[arg-type]
    assert interdit.value.status_code == 403

    v = await svc.valider(db, d.id, None, ADMIN_SCR)  # type: ignore[arg-type]
    assert v.statut == "valide" and v.poste_code == "SU000001"
    poste = (await db.execute(select(Poste).where(Poste.code == "SU000001"))).scalar_one()
    assert (poste.libelle, poste.feeder_id, poste.service_id) == ("Soraguin", 10, 5)
    lie = await db.get(SchemaUnifilairePoste, 2)
    assert lie is not None and (lie.poste_id, lie.rapprochement, lie.statut_sir) == (poste.id, "manuel", None)


async def test_rejet_et_inactif(db: AsyncSession) -> None:
    d = await svc.proposer(db, 1, 2, "Soraguin", 10, BCC)  # type: ignore[arg-type]
    with pytest.raises(HTTPException):
        await svc.definir_statut_sir(db, 1, 2, "inactif", BCC)  # type: ignore[arg-type]
    r = await svc.rejeter(db, d.id, "Poste démonté", ADMIN_SCR)  # type: ignore[arg-type]
    assert (r.statut, r.motif_rejet) == ("rejete", "Poste démonté")
    ligne = await svc.definir_statut_sir(db, 1, 2, "inactif", BCC)  # type: ignore[arg-type]
    assert ligne.statut_sir == "inactif"
    with pytest.raises(HTTPException) as lecture:
        await svc.definir_statut_sir(db, 1, 2, None, BRC_LECTURE)  # type: ignore[arg-type]
    assert lecture.value.status_code == 403


async def test_lier_sir_et_sig_a_la_main(db: AsyncSession) -> None:
    ligne = await svc.lier_sig(db, 1, 4, 9, ADMIN_SCR)  # type: ignore[arg-type]
    assert ligne.sig is not None and ligne.sig.nom_feeder == "Y" and ligne.rapprochement_sig == "manuel"
    await svc.rapprocher_sig(db, 1, ADMIN_SCR)  # type: ignore[arg-type]
    assert (await db.get(SchemaUnifilairePoste, 4)).noeud_sig_id == 9  # choix manuel gardé
    ligne = await svc.lier_sir(db, 1, 4, 101, ADMIN_SCR)  # type: ignore[arg-type]
    assert ligne.sir is not None and ligne.sir.feeder_libelle == "OUAKAM" and ligne.sir.poste_source_libelle == "HANN"


def test_interruption_programmee_deduite_de_la_nature() -> None:
    from app.services.interruption_distribution_service import _nature_programmee

    assert _nature_programmee(SimpleNamespace(code="COUPURE", libelle="Coupure travaux"))
    assert _nature_programmee(SimpleNamespace(code="X", libelle="Coupure programmée"))
    assert not _nature_programmee(SimpleNamespace(code="PERMANENT", libelle="Défaut permanent"))
    assert not _nature_programmee(None)
