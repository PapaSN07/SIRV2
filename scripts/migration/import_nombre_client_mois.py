#!/usr/bin/env python3
"""Import du nombre de clients par mois (dénominateur SAIFI/SAIDI SENELEC).

Source : srv-hfsql / SIR_ALHDL, table NombreClientMois
         (Annee, MoisNumerique, Nombreclient, ID_Service, IDAgence, IDDelegation, IDRegions).
Cible  : SIRV2 dbo.nombre_client_mois (service_id, annee, mois, nombre_clients).

Chaque ligne HFSQL est rattachée à un service SIRV2 : ID_Service, sinon le premier service de
IDAgence, sinon le service représentatif de la région (Dakar, Régions). Les lignes d'un même
service et d'un même mois sont additionnées, comme la mesure Power BI (SUM(Nombreclient)).

La simulation (par défaut) n'écrit rien : elle affiche le total national par mois, à comparer
avec Power BI, et le détail des lignes rejetées. Tester sur une copie de la base avant --execute.

Usage (poste ETL avec le pilote ODBC HFSQL, réseau SENELEC) :
    python scripts/migration/import_nombre_client_mois.py                 # simulation
    python scripts/migration/import_nombre_client_mois.py --depuis 2024   # à partir de 2024
    python scripts/migration/import_nombre_client_mois.py --execute       # écriture (upsert)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
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
from scripts.migration.transforms.rows import row_get  # noqa: E402

# Lignes régionales HFSQL (ID_Service = 0) → service représentatif (cf. loaders/indicateurs.py)
_REGION_SERVICE_LEGACY: dict[str, str] = {"15": "1", "16": "4"}


def _entier(valeur: Any) -> int:
    try:
        return int(float(str(valeur).strip()))
    except (TypeError, ValueError):
        return 0


def _services_par_agence(session) -> dict[int, int]:
    rows = session.execute(text("SELECT agence_id, MIN(id) FROM dbo.services GROUP BY agence_id")).all()
    return {int(a): int(s) for a, s in rows if a is not None}


def lire_hfsql() -> list[dict[str, Any]]:
    """Lecture directe (pas d'export JSONL éventuellement périmé)."""
    conn = connect_hfsql()
    try:
        return list(fetch_table(conn, "NombreClientMois"))
    finally:
        conn.close()


def agreger(
    rows: list[dict[str, Any]], id_maps: IdMapStore, services_agence: dict[int, int], depuis: int
) -> tuple[dict[tuple[int, int, int], int], Counter, list[dict[str, Any]], Counter]:
    totaux: dict[tuple[int, int, int], int] = defaultdict(int)
    niveaux: Counter = Counter()
    rejets: list[dict[str, Any]] = []
    national: Counter = Counter()
    for row in rows:
        annee = _entier(row_get(row, "Annee"))
        mois = _entier(row_get(row, "MoisNumerique", "Mois"))
        clients = _entier(row_get(row, "Nombreclient", "NombreClient"))
        ident = row_get(row, "IDClientAnnee")
        if annee < depuis:
            continue
        if not annee or not 1 <= mois <= 12:
            rejets.append({"id": ident, "motif": "période invalide", "annee": annee, "mois": mois})
            continue
        service_id = None
        niveau = ""
        legacy_svc = _entier(row_get(row, "ID_Service"))
        if legacy_svc > 0:
            service_id = id_maps.get("services", legacy_svc)
            niveau = "service"
        if service_id is None:
            legacy_agence = _entier(row_get(row, "IDAgence"))
            agence_id = id_maps.get("agences", legacy_agence) if legacy_agence > 0 else None
            if agence_id is not None:
                service_id = services_agence.get(int(agence_id))
                niveau = "agence"
        if service_id is None:
            legacy_region = str(_entier(row_get(row, "IDRegions")))
            legacy_rep = _REGION_SERVICE_LEGACY.get(legacy_region)
            if legacy_rep:
                service_id = id_maps.get("services", legacy_rep)
                niveau = "région"
        if service_id is None:
            rejets.append({"id": ident, "motif": "service introuvable", "annee": annee, "mois": mois, "clients": clients})
            continue
        niveaux[niveau] += 1
        totaux[(int(service_id), annee, mois)] += clients
        national[(annee, mois)] += clients
    return totaux, niveaux, rejets, national


def ecrire(session, totaux: dict[tuple[int, int, int], int]) -> dict[str, int]:
    bilan = {"inserees": 0, "mises_a_jour": 0, "inchangees": 0}
    existants = {
        (int(s), int(a), int(m)): int(n)
        for s, a, m, n in session.execute(
            text("SELECT service_id, annee, mois, nombre_clients FROM dbo.nombre_client_mois")
        ).all()
    }
    for (service_id, annee, mois), clients in totaux.items():
        avant = existants.get((service_id, annee, mois))
        if avant is None:
            session.execute(
                text(
                    "INSERT INTO dbo.nombre_client_mois (service_id, annee, mois, nombre_clients) "
                    "VALUES (:s, :a, :m, :n)"
                ),
                {"s": service_id, "a": annee, "m": mois, "n": clients},
            )
            bilan["inserees"] += 1
        elif avant != clients:
            session.execute(
                text(
                    "UPDATE dbo.nombre_client_mois SET nombre_clients = :n "
                    "WHERE service_id = :s AND annee = :a AND mois = :m"
                ),
                {"s": service_id, "a": annee, "m": mois, "n": clients},
            )
            bilan["mises_a_jour"] += 1
        else:
            bilan["inchangees"] += 1
    return bilan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Écrire en base (sinon simulation)")
    parser.add_argument("--depuis", type=int, default=2000, help="Première année importée")
    args = parser.parse_args()
    ensure_dirs()
    settings = get_settings()
    print(f"Source : {settings.hfsql_server} / {settings.hfsql_database} — table NombreClientMois")

    rows = lire_hfsql()
    print(f"{len(rows)} ligne(s) lue(s)")
    id_maps = IdMapStore()
    with get_session() as session:
        totaux, niveaux, rejets, national = agreger(rows, id_maps, _services_par_agence(session), args.depuis)
        print(f"Rattachement : {dict(niveaux)} · rejetées : {len(rejets)}")
        print("\nTotal national par mois (à comparer avec Power BI) :")
        for (annee, mois), clients in sorted(national.items())[-24:]:
            print(f"  {mois:02d}/{annee} : {clients:>10,}".replace(",", " "))
        bilan: dict[str, Any] = {"simulation": not args.execute, "service_mois": len(totaux)}
        if args.execute:
            bilan.update(ecrire(session, totaux))
        else:
            session.rollback()
    bilan["rejets"] = rejets[:50]
    print(json.dumps({k: v for k, v in bilan.items() if k != "rejets"}, ensure_ascii=False))
    rapport = settings.reports_dir / "import_nombre_client_mois.json"
    rapport.write_text(json.dumps(bilan, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Rapport : {rapport}")
    if not args.execute:
        print("\nSimulation : rien n'a été écrit. Relancer avec --execute, puis recalculer SAIFI/SAIDI :")
        print("  docker compose exec api python -m scripts.recalcul_saifi_saidi --depuis 2024-01")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
