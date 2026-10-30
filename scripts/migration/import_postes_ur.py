#!/usr/bin/env python3
"""Reprise du lien poste ↔ unité de relève de SIR v1 (PosteClient) dans dbo.postes_unites_releve.

SIR v1 (atelier SAIFI/SAIDI de l'application bureau) : PosteClient (IDPostes, UR, Nombreclient,
Agent_Modif, Agent_Valide). Une ligne par couple poste / unité de relève (UR, ex. 5420002P) ;
les clients d'un poste sont la somme des contrats de ses UR.

  - poste : IDPostes SIR v1 → poste SIRV2 (table de correspondance de la reprise « postes ») ;
  - UR    : colonne UR, à défaut Codereference ;
  - statut « valide » (liens en service dans SIR v1).

Relancer ne crée pas de doublon (couple poste / UR unique). Les clients des postes sont recalculés
à la synchronisation suivante (chaque jour à 7 h, ou bouton « Synchroniser » de la page Base clients).

Usage (poste ETL avec le pilote ODBC HFSQL, réseau SENELEC) :
    python scripts/migration/import_postes_ur.py              # simulation
    python scripts/migration/import_postes_ur.py --execute
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_table  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.import_repertoire_sms import champ  # noqa: E402

_RE_UR = re.compile(r"^[0-9A-Z]{4,20}$")


def preparer(rows: list[dict[str, Any]], postes: dict[str, int]) -> tuple[set[tuple[int, str]], Counter]:
    """Couples (poste SIRV2, UR) et décompte des lignes écartées."""
    liens: set[tuple[int, str]] = set()
    rejets: Counter = Counter()
    for row in rows:
        ur = (champ(row, "UR") or champ(row, "Codereference")).upper().replace(" ", "")
        if not _RE_UR.match(ur):
            rejets["UR absente ou invalide"] += 1
            continue
        poste_id = postes.get(champ(row, "IDPostes").split(".")[0])
        if poste_id is None:
            rejets["poste inconnu dans SIRV2"] += 1
            continue
        if (poste_id, ur) in liens:
            rejets["lien en double"] += 1
            continue
        liens.add((poste_id, ur))
    return liens, rejets


def ecrire(session, liens: set[tuple[int, str]], simulation: bool = True) -> dict[str, int]:
    """Insère les liens absents. En simulation, compte seulement (rien n'est envoyé à la base)."""
    existants = {
        (int(p), str(u)) for p, u in session.execute(text("SELECT poste_id, unite_releve FROM dbo.postes_unites_releve")).all()
    }
    nouveaux = sorted(liens - existants)
    if not simulation and nouveaux:
        # fast_executemany : un envoi groupé par lot au lieu d'un aller-retour par ligne (65 000 liens)
        cur = session.connection().connection.cursor()
        cur.fast_executemany = True
        for i in range(0, len(nouveaux), 5000):
            cur.executemany(
                "INSERT INTO dbo.postes_unites_releve (poste_id, unite_releve, statut) VALUES (?, ?, 'valide')",
                nouveaux[i : i + 5000],
            )
            print(f"  {min(i + 5000, len(nouveaux))} / {len(nouveaux)}", flush=True)
        cur.close()
    return {"liens_crees": len(nouveaux), "liens_deja_presents": len(liens & existants)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    args = parser.parse_args()
    ensure_dirs()
    settings = get_settings()
    print(f"Source : {settings.hfsql_server} / {settings.hfsql_database} — table PosteClient")
    conn = connect_hfsql()
    try:
        rows = list(fetch_table(conn, "PosteClient"))
    finally:
        conn.close()
    postes = {str(k): int(v) for k, v in IdMapStore().load("postes").items()}
    liens, rejets = preparer(rows, postes)
    print(f"{len(rows)} ligne(s) lue(s) → {len(liens)} lien(s), {len({p for p, _ in liens})} poste(s), "
          f"{len({u for _, u in liens})} UR")
    if rejets:
        print(f"Écartés : {dict(rejets)}")
    bilan: dict[str, Any] = {"simulation": not args.execute, "lus": len(rows), "liens": len(liens)}
    with get_session() as session:
        bilan.update(ecrire(session, liens, simulation=not args.execute))
    print(json.dumps(bilan, ensure_ascii=False))
    (settings.reports_dir / "import_postes_ur.json").write_text(
        json.dumps({**bilan, "rejets": dict(rejets)}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
