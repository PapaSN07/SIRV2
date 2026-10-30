"""Reprise d'une période récente : plan des étapes et limite de la base clients HFSQL."""

import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
# sir-backend/scripts porte le même nom de paquet : forcer celui de la racine du dépôt
if "scripts" in sys.modules and not hasattr(sys.modules["scripts"], "migration"):
    for nom in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[nom]

from scripts.migration.delta_periode import commandes, dernier_mois_hfsql_clients  # noqa: E402
from scripts.migration.import_nombre_client_mois import agreger  # noqa: E402


def test_dernier_mois_avant_bi_ods() -> None:
    assert dernier_mois_hfsql_clients(["2026-10", "2026-11"]) == "2026-09"
    assert dernier_mois_hfsql_clients(["2027-01"]) == "2026-12"
    assert dernier_mois_hfsql_clients([]) is None


def test_plan_depuis_juin() -> None:
    plan = commandes(datetime(2026, 6, 1), "2026-09")
    assert plan["clients"][0][-2:] == ["--jusqu-a", "2026-09"]
    assert plan["postes"][0][-2:] == ["--depuis", "2026-06-01"]
    assert "--avec-transport" in plan["interruptions"][0]
    assert "--jusqu-a" not in commandes(datetime(2026, 6, 1), None)["clients"][0]


class _Maps:
    def get(self, entite: str, legacy: object) -> int | None:
        return 5 if entite == "services" else None


def test_nombre_client_mois_borne() -> None:
    rows = [
        {"Annee": 2026, "MoisNumerique": m, "Nombreclient": 10, "ID_Service": 1, "IDClientAnnee": m}
        for m in (5, 6, 9, 10)
    ]
    totaux, *_ = agreger(rows, _Maps(), {}, 2026, (2026, 9))  # type: ignore[arg-type]
    assert sorted(m for (_, _, m) in totaux) == [5, 6, 9]
