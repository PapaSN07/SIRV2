"""Région d'exploitation portée par l'interruption : Dakar (BCC) / Régions (BRC)."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
if "scripts" in sys.modules and not hasattr(sys.modules["scripts"], "migration"):
    for nom in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[nom]

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects import mssql  # noqa: E402

from app.models.interruptions import Interruption  # noqa: E402
from app.repositories import perimetre  # noqa: E402
from app.repositories.interruption_distribution_repository import _apply_scope  # noqa: E402
from app.repositories.reseau_distribution_repository import ScopeFilter  # noqa: E402
from scripts.migration.backfill_interruption_region import corrections  # noqa: E402
from scripts.migration.transforms.regions import code_region_v1  # noqa: E402



def _sql(condition) -> str:
    return str(select(Interruption.id).where(condition).compile(dialect=mssql.dialect()))


def test_perimetre_national_puis_region() -> None:
    perimetre.definir_region(None)
    assert "region_id" not in _sql(perimetre.interruptions_du_perimetre([1, 2]))
    with perimetre.perimetre_region(2):
        sql = _sql(perimetre.interruptions_du_perimetre([1, 2]))
        assert "interruptions.region_id = " in sql
        clients = _sql(perimetre.clients_du_perimetre([1, 2]))
        assert "services.region_id = " in clients
    assert perimetre.region_courante() is None


def test_scope_bcc_brc_sur_la_region_de_l_interruption() -> None:
    requete = _apply_scope(select(Interruption.id), ScopeFilter(region_id=1))
    sql = str(requete.compile(dialect=mssql.dialect()))
    assert "interruptions.region_id = " in sql and "services" not in sql


def test_code_region_v1() -> None:
    assert code_region_v1("Dakar") == "DAKAR"
    assert code_region_v1(" Régions ") == "REGIONS" and code_region_v1("REGIONS") == "REGIONS"
    assert code_region_v1("TRANSPORT") is None and code_region_v1(None) is None


def test_backfill_region_corrections() -> None:
    # (id, région actuelle, région du départ) : 10 → Dakar ; 11 Dakar → Régions ; 12 juste ; 13 inconnue
    lignes = [(10, None, 1), (11, 1, 2), (12, 2, 2), (13, None, None)]
    assert corrections(lignes) == [(1, 10), (2, 11)]
