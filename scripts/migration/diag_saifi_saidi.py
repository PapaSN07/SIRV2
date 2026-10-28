#!/usr/bin/env python3
"""Diagnostic SAIFI/SAIDI d'un mois : SIR v1 (HFSQL, formule Power BI) contre SIRV2.

Lecture seule des deux côtés. Calcule, pour le mois demandé et au niveau national :
- côté HFSQL : NombreClient = Σ PosteInterruption.nombreclientposteEstime,
  SAIDI = Σ (NombreClient × Interruptions.dureeHeure) ;
- côté SIRV2 : la même chose avec poste_interruptions et interruptions.duree_minutes / 60,

puis liste les écarts interruption par interruption (clients, durée, statut) et écrit
le détail dans reports/diag_saifi_saidi_AAAA-MM.csv.

Usage (poste ETL avec le pilote ODBC HFSQL, comme import_nombre_client_mois) :
    python scripts/migration/diag_saifi_saidi.py --mois 2026-05
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402

_STATUTS_COMPTES = ("cloture", "valide", "archive")


def _f(valeur: Any) -> float:
    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _bornes(mois: str) -> tuple[int, int, str, str]:
    annee, m = (int(x) for x in mois.split("-"))
    suivant = (annee + (m == 12), m % 12 + 1)
    return annee, m, f"{annee:04d}{m:02d}01", f"{suivant[0]:04d}{suivant[1]:02d}01"


def lire_hfsql(debut: str, fin: str) -> dict[str, dict[str, Any]]:
    """Interruptions du mois (HFSQL) avec leurs clients estimés."""
    conn = connect_hfsql()
    try:
        requetes = [
            f"SELECT NInterruption, NumeroInterruption, DateApparition, dureeHeure, IDService, "
            f"Nature, casforcemajeur, Validation, Directionimputable, Duree_Jrs, DureeInterruption "
            f"FROM Interruptions WHERE DateApparition >= '{d}' AND DateApparition < '{f}'"
            for d, f in ((debut, fin), (f"{debut[:4]}-{debut[4:6]}-01", f"{fin[:4]}-{fin[4:6]}-01"))
        ]
        lignes: list[dict[str, Any]] = []
        for requete in requetes:
            try:
                lignes = fetch_all(conn, requete)
                break
            except Exception as exc:  # format de date refusé : essai suivant
                print(f"  (requête HFSQL refusée : {str(exc)[:100]})")
        interruptions: dict[str, dict[str, Any]] = {}
        for row in lignes:
            cle = str(row_get(row, "NInterruption")).split(".")[0]
            interruptions[cle] = {
                "numero": row_get(row, "NumeroInterruption"),
                "duree_h": _f(row_get(row, "dureeHeure")),
                "nature": str(row_get(row, "Nature") or "?").strip() or "?",
                "force_majeure": str(row_get(row, "casforcemajeur")),
                "validation": str(row_get(row, "Validation")),
                "imputable": str(row_get(row, "Directionimputable") or "?").strip() or "?",
                "duree_jrs": _f(row_get(row, "Duree_Jrs")),
                "duree_brute": _f(row_get(row, "DureeInterruption")),
                "clients": 0.0,
                "postes": 0,
            }
        ids = list(interruptions)
        for i in range(0, len(ids), 200):
            paquet = ",".join(ids[i : i + 200])
            for row in fetch_all(
                conn,
                "SELECT NInterruption, COUNT(*) AS nb, SUM(nombreclientposteEstime) AS clients "
                f"FROM PosteInterruption WHERE NInterruption IN ({paquet}) GROUP BY NInterruption",
            ):
                cle = str(row_get(row, "NInterruption")).split(".")[0]
                if cle in interruptions:
                    interruptions[cle]["clients"] = _f(row_get(row, "clients"))
                    interruptions[cle]["postes"] = int(_f(row_get(row, "nb")))
        return interruptions
    finally:
        conn.close()


def lire_sirv2(session, annee: int, mois: int) -> dict[int, dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT i.id, i.numero_interruption, i.statut, i.duree_minutes, i.date_apparition,
                   i.date_remise,
                   COUNT(pi.id) AS postes,
                   SUM(CAST(COALESCE(pi.nombre_clients_estime, pi.nombre_clients_touches, 0) AS BIGINT))
                       AS clients,
                   SUM(CAST(COALESCE(pi.nombre_clients_touches, 0) AS BIGINT)) AS touches
            FROM dbo.interruptions i
            LEFT JOIN dbo.poste_interruptions pi ON pi.interruption_id = i.id
            WHERE i.type_direction = 'distribution'
              AND YEAR(i.date_apparition) = :a AND MONTH(i.date_apparition) = :m
            GROUP BY i.id, i.numero_interruption, i.statut, i.duree_minutes, i.date_apparition,
                     i.date_remise
            """
        ),
        {"a": annee, "m": mois},
    ).mappings()
    return {
        int(r["id"]): {
            "numero": r["numero_interruption"],
            "statut": r["statut"],
            "duree_h": (r["duree_minutes"] or 0) / 60.0,
            "apparition": r["date_apparition"],
            "remise": r["date_remise"],
            "postes": int(r["postes"] or 0),
            "clients": float(r["clients"] or 0),
            "touches": float(r["touches"] or 0),
        }
        for r in rows
    }


def _resume(titre: str, lignes: list[dict[str, Any]], base: int) -> None:
    clients = sum(x["clients"] for x in lignes)
    ch = sum(x["clients"] * x["duree_h"] for x in lignes)
    durees = sorted(x["duree_h"] for x in lignes) or [0.0]
    print(f"\n{titre}")
    print(f"  interruptions        : {len(lignes):>12,}".replace(",", " "))
    print(f"  Σ clients            : {clients:>12,.0f}".replace(",", " "))
    print(f"  Σ clients × durée (h): {ch:>16,.1f}".replace(",", " "))
    print(
        f"  durée (h) médiane {statistics.median(durees):.2f} · p99 "
        f"{durees[int(len(durees) * 0.99) - 1 if len(durees) > 1 else 0]:.1f} · max {durees[-1]:.1f}"
    )
    if base:
        print(f"  SAIFI = {clients / base:.4f}   SAIDI = {ch / base:.4f}")


def _ventilations(lignes: list[dict[str, Any]], base: int) -> None:
    """Pistes pour retrouver la valeur Power BI : sous-ensembles et autres durées."""
    if not base or not lignes:
        return
    print("\n  Ventilation HFSQL (SAIFI / SAIDI de chaque sous-ensemble) :")
    for champ in ("nature", "force_majeure", "validation", "imputable"):
        groupes: dict[str, list[dict[str, Any]]] = {}
        for x in lignes:
            groupes.setdefault(x[champ], []).append(x)
        for valeur, groupe in sorted(groupes.items(), key=lambda kv: -len(kv[1]))[:8]:
            cli = sum(x["clients"] for x in groupe)
            ch = sum(x["clients"] * x["duree_h"] for x in groupe)
            print(f"    {champ:<14} {valeur[:24]:<24} {len(groupe):>6} interr.  SAIFI {cli / base:.4f}  SAIDI {ch / base:.4f}")
    for seuil in (3, 5):
        longues = [x for x in lignes if x["duree_h"] * 60 > seuil]
        cli = sum(x["clients"] for x in longues)
        ch = sum(x["clients"] * x["duree_h"] for x in longues)
        print(f"    durée > {seuil} min       {len(longues):>6} interr.  SAIFI {cli / base:.4f}  SAIDI {ch / base:.4f}")
    ch_jrs = sum(x["clients"] * x["duree_jrs"] * 24 for x in lignes)
    print(f"    SAIDI avec Duree_Jrs × 24 : {ch_jrs / base:.4f}")
    paires = [(x["duree_brute"], x["duree_h"]) for x in lignes if x["duree_h"] > 0 and x["duree_brute"] > 0]
    if paires:
        ratios = sorted(b / h for b, h in paires)
        print(f"    DureeInterruption / dureeHeure (médiane) : {ratios[len(ratios) // 2]:.1f}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mois", required=True, help="AAAA-MM")
    args = parser.parse_args()
    ensure_dirs()
    annee, mois, debut, fin = _bornes(args.mois)

    print(f"Diagnostic SAIFI/SAIDI national {mois:02d}/{annee}")
    hfsql = lire_hfsql(debut, fin)
    legacy_vers_id = {str(k).split(".")[0]: int(v) for k, v in IdMapStore().load("interruptions").items()}
    with get_session() as session:
        sirv2 = lire_sirv2(session, annee, mois)
        base = int(
            session.execute(
                text("SELECT COALESCE(SUM(nombre_clients), 0) FROM dbo.nombre_client_mois WHERE annee = :a AND mois = :m"),
                {"a": annee, "m": mois},
            ).scalar()
            or 0
        )
        session.rollback()

    print(f"Base clients (NombreClientMois) : {base:,}".replace(",", " "))
    _resume("HFSQL (formule Power BI)", list(hfsql.values()), base)
    _ventilations(list(hfsql.values()), base)
    comptees = [x for x in sirv2.values() if x["statut"] in _STATUTS_COMPTES and x["remise"] is not None]
    _resume("SIRV2 — interruptions comptées (clôturées/validées/archivées)", comptees, base)
    _resume("SIRV2 — toutes les interruptions du mois", list(sirv2.values()), base)
    statuts: dict[str, int] = {}
    for x in sirv2.values():
        statuts[x["statut"]] = statuts.get(x["statut"], 0) + 1
    print(f"  statuts SIRV2 : {statuts}")

    # Rapprochement interruption par interruption
    ecarts: list[dict[str, Any]] = []
    vus: set[int] = set()
    for legacy, h in hfsql.items():
        sid = legacy_vers_id.get(legacy)
        s = sirv2.get(sid) if sid else None
        if sid:
            vus.add(sid)
        ecarts.append(
            {
                "ninterruption": legacy,
                "sirv2_id": sid,
                "numero": h["numero"],
                "statut_sirv2": s["statut"] if s else "ABSENTE",
                "clients_hfsql": h["clients"],
                "clients_sirv2": s["clients"] if s else 0,
                "touches_sirv2": s["touches"] if s else 0,
                "postes_hfsql": h["postes"],
                "postes_sirv2": s["postes"] if s else 0,
                "duree_h_hfsql": round(h["duree_h"], 3),
                "duree_h_sirv2": round(s["duree_h"], 3) if s else 0,
                "ch_hfsql": h["clients"] * h["duree_h"],
                "ch_sirv2": (s["clients"] * s["duree_h"]) if s else 0,
            }
        )
    for sid, s in sirv2.items():
        if sid not in vus:
            ecarts.append(
                {
                    "ninterruption": None, "sirv2_id": sid, "numero": s["numero"],
                    "statut_sirv2": s["statut"], "clients_hfsql": 0, "clients_sirv2": s["clients"],
                    "touches_sirv2": s["touches"], "postes_hfsql": 0, "postes_sirv2": s["postes"],
                    "duree_h_hfsql": 0, "duree_h_sirv2": round(s["duree_h"], 3),
                    "ch_hfsql": 0, "ch_sirv2": s["clients"] * s["duree_h"],
                }
            )

    absentes = sum(1 for e in ecarts if e["statut_sirv2"] == "ABSENTE")
    seulement_sirv2 = sum(1 for e in ecarts if e["ninterruption"] is None)
    print(f"\nRapprochement : {absentes} interruption(s) HFSQL absente(s) de SIRV2, "
          f"{seulement_sirv2} interruption(s) SIRV2 sans équivalent HFSQL sur ce mois")
    diff_clients = sum(1 for e in ecarts if e["ninterruption"] and abs(e["clients_hfsql"] - e["clients_sirv2"]) > 0.5)
    diff_duree = sum(1 for e in ecarts if e["ninterruption"] and abs(e["duree_h_hfsql"] - e["duree_h_sirv2"]) > 0.05)
    print(f"  clients différents : {diff_clients} · durées différentes : {diff_duree}")

    print("\n10 plus gros écarts de clients × durée (h) :")
    print(f"  {'NInterr.':>10} {'SIRV2':>8} {'statut':<9} {'cli HF':>8} {'cli V2':>8} {'h HF':>8} {'h V2':>9}")
    for e in sorted(ecarts, key=lambda e: abs(e["ch_sirv2"] - e["ch_hfsql"]), reverse=True)[:10]:
        print(
            f"  {str(e['ninterruption']):>10} {str(e['sirv2_id']):>8} {e['statut_sirv2']:<9} "
            f"{e['clients_hfsql']:>8.0f} {e['clients_sirv2']:>8.0f} {e['duree_h_hfsql']:>8.2f} {e['duree_h_sirv2']:>9.2f}"
        )

    rapport = get_settings().reports_dir / f"diag_saifi_saidi_{annee}-{mois:02d}.csv"
    with rapport.open("w", newline="", encoding="utf-8-sig") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=list(ecarts[0]) if ecarts else ["vide"], delimiter=";")
        writer.writeheader()
        writer.writerows(ecarts)
    print(f"\nDétail : {rapport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
