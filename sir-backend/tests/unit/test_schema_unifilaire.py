"""Schémas unifilaires : postes entre deux postes, rapprochement par le nom, API."""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import mssql

from app.models.schema_unifilaire import SchemaUnifilaireTuile
from app.services import schema_unifilaire_service as svc
from app.services.schema_unifilaire_graphe import Graphe, postes_entre
from app.services.schema_unifilaire_rapprochement import cle_poste, rapprocher


def _graphe(aretes: list[tuple[int, int]], postes: list[int], n: int) -> Graphe:
    return Graphe.depuis_json(
        {"coords": [[i * 10, 0] for i in range(n)], "aretes": [[a, b, 10] for a, b in aretes], "postes": postes}
    )


def test_postes_le_long_de_la_ligne_dans_l_ordre() -> None:
    # Boucle Dakar : P0 - P1 - P2 - P3 - P4 (nœuds 0..4), postes = nœuds
    g = _graphe([(0, 1), (1, 2), (2, 3), (3, 4)], postes=[0, 1, 2, 3, 4], n=5)
    r = postes_entre(g, 1, 3)
    assert r is not None
    assert r.rangs_chemin == [1, 2, 3]
    assert r.rangs_antennes == [] and r.derivations == []
    assert len(r.trace) == 3


def test_antennes_et_derivations_ne_depassent_pas_les_bornes() -> None:
    # Ligne A(0) - j1(1) - j2(2) - B(3) - au-delà(4) ; antenne P5 sur j1 ; dérivation P6-P7 sur j2 ;
    # branche j1 - 8 - 4 qui rejoint le réseau au-delà de B : exclue
    aretes = [(0, 1), (1, 2), (2, 3), (3, 4), (1, 5), (2, 6), (6, 7), (1, 8), (8, 4)]
    g = _graphe(aretes, postes=[0, 3, 5, 6, 7, 4], n=9)
    r = postes_entre(g, 0, 1)
    assert r is not None
    assert r.rangs_chemin == [0, 1]
    assert r.rangs_antennes == [2]
    assert [d.rangs for d in r.derivations] == [[3, 4]]
    # P4 (au-delà de B, rang 5) n'est jamais proposé
    assert 5 not in r.rangs_chemin + r.rangs_antennes + [x for d in r.derivations for x in d.rangs]


def test_postes_non_relies() -> None:
    g = _graphe([(0, 1)], postes=[0, 2], n=3)
    assert postes_entre(g, 0, 1) is None


def test_cle_poste_et_rapprochement() -> None:
    assert cle_poste("H61 Lycée Mbeuleukhé (400 kVA)") == "LYCEE MBEULEUKHE"
    assert cle_poste("CM Ipres Almadies 1") == "IPRES ALMADIES 1"
    assert cle_poste("H61 Mbaye Awa C") == "MBAYE AWA"
    postes = [(1, "LYCEE MBEULEUKHE", "P1"), (2, "Ipres Almadies 1", None), (3, "Kébé", None), (4, "KEBE", None)]
    res = rapprocher(["H61 Lycée Mbeuleukhé", "Ipres-Almadies 1", "Kébé", "Inconnu", None], postes)
    assert res == [(1, "auto"), (2, "auto"), (None, "ambigu"), (None, None), (None, None)]


def test_tuile_requete_sql_server() -> None:
    requete = select(SchemaUnifilaireTuile.contenu).where(
        SchemaUnifilaireTuile.schema_id == 1, SchemaUnifilaireTuile.z == 3
    )
    sql = str(requete.compile(dialect=mssql.dialect()))
    assert "schema_unifilaire_tuiles" in sql


@pytest.mark.asyncio
async def test_service_entre_avec_graphe_en_cache() -> None:
    graphe = gzip.compress(
        json.dumps({"coords": [[0, 0], [5, 0], [10, 0]], "aretes": [[0, 1, 5], [1, 2, 5]], "postes": [0, 1, 2]}).encode()
    )
    schema = SimpleNamespace(id=9, is_active=True, importe_le=datetime(2026, 11, 20), region=None)
    postes = [
        SimpleNamespace(
            id=100 + r, rang=r, libelle=f"P{r}", forme="carre", puissance_kva=None, x0=0, y0=0, x1=1, y1=1,
            lx0=None, ly0=None, lx1=None, ly1=None, poste_id=r + 1, rapprochement="auto", __dict__={},
        )
        for r in range(3)
    ]
    for p in postes:
        p.__dict__.update({"poste": None})
    with (
        patch.object(svc.repo, "obtenir", AsyncMock(return_value=schema)),
        patch.object(svc.repo, "postes", AsyncMock(return_value=postes)),
        patch.object(svc.repo, "graphe", AsyncMock(return_value=graphe)) as lu,
    ):
        r1 = await svc.entre(AsyncMock(), 9, 100, 102)
        await svc.entre(AsyncMock(), 9, 102, 100)
    assert [p.libelle for p in r1.chemin] == ["P0", "P1", "P2"]
    assert lu.await_count == 1  # graphe lu une fois, puis gardé en mémoire


@pytest.mark.asyncio
async def test_ajout_en_lot_sans_controle_de_feeder() -> None:
    """Postes choisis sur le schéma : tous feeders, doublons et postes inconnus comptés à part."""
    from app.services import interruption_distribution_service as isvc

    interruption = SimpleNamespace(id=5, statut="en_cours")
    postes = {1: SimpleNamespace(id=1, is_active=True), 2: SimpleNamespace(id=2, is_active=True)}
    bulk = AsyncMock(return_value=isvc.PosteImpacteBulkResponse(added_count=2, skipped_count=0))
    with (
        patch.object(isvc, "_get_interruption_accessible", AsyncMock(return_value=interruption)),
        patch.object(isvc, "_ensure_statut_en_cours"),
        patch.object(isvc.reseau_repo, "get_poste", AsyncMock(side_effect=lambda db, i: postes.get(i))),
        patch.object(isvc, "_bulk_link_postes", bulk),
    ):
        res = await isvc.add_postes_lot(AsyncMock(), 5, [1, 2, 2, 99], SimpleNamespace(id=1))
    assert bulk.await_args.kwargs["verifier_perimetre"] is False
    assert [p.id for p in bulk.await_args.args[2]] == [1, 2]
    assert res.skipped_count == 1  # le poste 99 inconnu
