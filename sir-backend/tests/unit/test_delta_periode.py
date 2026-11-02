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
    assert "--avec-transport" not in plan["interruptions"][0]  # transport en attente
    assert "--avec-transport" in commandes(datetime(2026, 6, 1), None, True)["interruptions"][0]
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


def test_saisies_test_hors_reprise() -> None:
    from types import SimpleNamespace

    from scripts.migration.supprimer_saisies_test import a_supprimer

    rows = [SimpleNamespace(id=i) for i in (1, 2, 3, 4)]
    assert [r.id for r in a_supprimer(rows, {1, 2}, None)] == [3, 4]
    assert [r.id for r in a_supprimer(rows, {1, 2}, {4, 1})] == [4]


def test_colonnes_absentes_retirees_du_select() -> None:
    from scripts.migration.hfsql_schema import filtrer_colonnes

    gardees, absentes = filtrer_colonnes(["NInterruption", "idservice", "Service"], {"ninterruption", "service"})
    assert gardees == ["NInterruption", "Service"] and absentes == ["idservice"]
    assert filtrer_colonnes(["A"], None) == (["A"], [])


def test_diag_interruptions_end_ecarts() -> None:
    from scripts.migration.diag_interruptions_end import _vrai, compte_ecran, ecarts_interruption

    base = {
        "apparition": datetime(2026, 9, 1, 8, 0),
        "remise": datetime(2026, 9, 1, 9, 0),
        "end": 1.25,
        "puissance_mw": 0.5,
        "force_majeure": False,
        "statut": "valide",
        "service_id": 3,
    }
    assert ecarts_interruption(base, dict(base)) == []
    autre = {**base, "end": 1.3, "remise": datetime(2026, 9, 1, 9, 5), "force_majeure": True, "statut": "archive"}
    assert ecarts_interruption(base, autre) == ["remise", "end", "force_majeure"]  # archive et valide comptent tous deux
    assert not _vrai("0") and _vrai(1) and _vrai("Vrai") and not _vrai(None)
    assert compte_ecran(base) and not compte_ecran({**base, "statut": "en_cours"})
