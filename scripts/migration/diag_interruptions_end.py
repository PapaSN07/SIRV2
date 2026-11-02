#!/usr/bin/env python3
"""Contrôle de la reprise : nombre d'interruptions et END, SIR v1 (HFSQL) contre SIRV2.

Lecture seule des deux côtés, interruptions de distribution apparues entre --depuis et --jusqu-a.

1. Par mois d'apparition : nombre d'interruptions et Σ ENDD (brut) de chaque côté.
2. Par mois de remise, avec les filtres des écrans SIRV2 (clôturée / validée / archivée, hors
   force majeure) : nombre et END, appliqués aux deux côtés.
3. Par région : nombre et END sur la période.
4. Interruption par interruption : absentes d'un côté, écarts de date d'apparition ou de remise,
   de statut, de force majeure, de service, d'END et de puissance coupée ; détail en CSV.
5. Unité de l'END : rapport END / (puissance coupée × durée) des deux côtés (SIR v1 en kWh, SIRV2 en MWh) ;
   ENDD de SIR v1 est en kWh : il est ramené en MWh (÷ 1000) pour toutes les comparaisons.

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/diag_interruptions_end.py --depuis 2026-06 --jusqu-a 2026-10
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
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
from scripts.migration.hfsql_schema import _colonnes_reelles, filtrer_colonnes  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.transforms.dates import (  # noqa: E402
    resolve_interruption_date_apparition,
    resolve_interruption_date_remise,
)
from scripts.migration.transforms.fk_resolver import FkResolver  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402
from scripts.migration.transforms.statut import map_statut  # noqa: E402

COMPTES = ("cloture", "valide", "archive")
_COLONNES_HF = [
    "NInterruption",
    "DateApparition",
    "heureApparition",
    "DateRemise",
    "heureremise",
    "DateFinRemise",
    "Creation",
    "Modification",
    "Annee",
    "dureeHeure",
    "ENDD",
    "PuissanceCoupee",
    "casforcemajeur",
    "Validation",
    "indicateurvalidation",
    "EtatTraitement",
    "Service",
    "idservice",
    "Feeder",
    "idfeeder",
    "supprimer",
]
_TOL_END = 0.001  # MWh
_TOL_MINUTES = 1


def _f(valeur: Any) -> float | None:
    if valeur is None or str(valeur).strip() == "":
        return None
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return None


def _vrai(valeur: Any) -> bool:
    """Booléen HFSQL : 1, « 1 », True, « Vrai »… (bool("0") vaut True en Python)."""
    return str(valeur).strip().lower() in ("1", "true", "vrai", "oui", "-1")


def _mois(d: datetime | None) -> str:
    return f"{d.year}-{d.month:02d}" if d else "—"


def lire_hfsql(depuis: str, fin: str) -> list[dict[str, Any]]:
    conn = connect_hfsql()
    try:
        colonnes, absentes = filtrer_colonnes(
            _COLONNES_HF, _colonnes_reelles(conn, "Interruptions")
        )
        if absentes:
            print(f"  (colonnes absentes d'Interruptions : {', '.join(absentes)})")
        return fetch_all(
            conn,
            f"SELECT {', '.join(colonnes)} FROM Interruptions "
            f"WHERE DateApparition >= '{depuis.replace('-', '')}01' AND DateApparition < '{fin.replace('-', '')}01'",
        )
    finally:
        conn.close()


def normaliser_hfsql(
    rows: list[dict[str, Any]], fk: FkResolver
) -> dict[str, dict[str, Any]]:
    resultat: dict[str, dict[str, Any]] = {}
    for row in rows:
        cle = str(row_get(row, "NInterruption")).split(".")[0]
        puissance_kw = _f(row_get(row, "PuissanceCoupee", "puissancecoupee"))
        resultat[cle] = {
            "apparition": resolve_interruption_date_apparition(row),
            "remise": resolve_interruption_date_remise(row),
            "duree_h": _f(row_get(row, "dureeHeure", "dureeheure")),
            "end": (_f(row_get(row, "ENDD", "endd")) or 0.0) / 1000,  # kWh → MWh
            "puissance_mw": puissance_kw * 0.001 if puissance_kw is not None else None,
            "force_majeure": _vrai(row_get(row, "casforcemajeur")),
            "statut": map_statut(
                row_get(row, "EtatTraitement"),
                row_get(row, "Validation", "indicateurvalidation"),
                False,
            ),
            "service_id": fk.resolve_service_id(row),
            "supprimee": _vrai(row_get(row, "supprimer")),
        }
    return resultat


def lire_sirv2(
    session, depuis: datetime, fin: datetime
) -> tuple[dict[int, dict[str, Any]], dict[int, tuple[str, str]]]:
    rows = session.execute(
        text(
            "SELECT i.id, i.date_apparition, i.date_remise, i.duree_minutes, i.statut, i.is_force_majeure, "
            "i.service_id, i.puissance_coupee_mw, d.end_mwh "
            "FROM dbo.interruptions i LEFT JOIN dbo.interruptions_distribution d ON d.interruption_id = i.id "
            "WHERE i.type_direction = 'distribution' AND i.date_apparition >= :d AND i.date_apparition < :f"
        ),
        {"d": depuis, "f": fin},
    ).all()
    services = {
        int(s): (str(lib), str(reg or "—"))
        for s, lib, reg in session.execute(
            text(
                "SELECT s.id, s.libelle, r.libelle FROM dbo.services s LEFT JOIN dbo.regions r ON r.id = s.region_id"
            )
        ).all()
    }
    return {
        int(r.id): {
            "apparition": r.date_apparition,
            "remise": r.date_remise,
            "duree_h": (r.duree_minutes or 0) / 60
            if r.duree_minutes is not None
            else None,
            "end": float(r.end_mwh or 0),
            "puissance_mw": float(r.puissance_coupee_mw)
            if r.puissance_coupee_mw is not None
            else None,
            "force_majeure": bool(r.is_force_majeure),
            "statut": r.statut,
            "service_id": r.service_id,
        }
        for r in rows
    }, services


def ecarts_interruption(hf: dict[str, Any], v2: dict[str, Any]) -> list[str]:
    champs: list[str] = []
    for nom in ("apparition", "remise"):
        a, b = hf[nom], v2[nom]
        if (a is None) != (b is None) or (
            a and b and abs((a - b).total_seconds()) > _TOL_MINUTES * 60
        ):
            champs.append(nom)
    if abs(hf["end"] - v2["end"]) > _TOL_END:
        champs.append("end")
    pa, pb = hf["puissance_mw"], v2["puissance_mw"]
    if (pa is None) != (pb is None) or (
        pa is not None and pb is not None and abs(pa - pb) > 0.0005
    ):
        champs.append("puissance")
    if hf["force_majeure"] != v2["force_majeure"]:
        champs.append("force_majeure")
    if (hf["statut"] in COMPTES) != (v2["statut"] in COMPTES):
        champs.append("statut")
    if hf["service_id"] is not None and hf["service_id"] != v2["service_id"]:
        champs.append("service")
    return champs


def compte_ecran(x: dict[str, Any]) -> bool:
    """Filtre des écrans END de SIRV2 : clôturée / validée / archivée, hors force majeure, remise connue."""
    return x["statut"] in COMPTES and not x["force_majeure"] and x["remise"] is not None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--depuis", required=True, help="Premier mois (AAAA-MM)")
    parser.add_argument(
        "--jusqu-a", required=True, help="Dernier mois inclus (AAAA-MM)"
    )
    args = parser.parse_args()
    ensure_dirs()
    annee, mois = (int(x) for x in args.jusqu_a.split("-"))
    fin_mois = f"{annee + (mois == 12)}-{mois % 12 + 1:02d}"
    debut_dt = datetime.strptime(args.depuis, "%Y-%m")
    fin_dt = datetime.strptime(fin_mois, "%Y-%m")

    id_maps = IdMapStore()
    sir_par_legacy = {str(k): int(v) for k, v in id_maps.load("interruptions").items()}
    print(
        f"Lecture SIR v1 (Interruptions, {args.depuis} → {args.jusqu_a})…", flush=True
    )
    hf = normaliser_hfsql(lire_hfsql(args.depuis, fin_mois), FkResolver(id_maps))
    with get_session() as session:
        v2, services = lire_sirv2(session, debut_dt, fin_dt)
        session.rollback()
    supprimees = sum(1 for x in hf.values() if x["supprimee"])
    print(
        f"SIR v1 : {len(hf)} interruption(s) (dont {supprimees} marquée(s) « supprimer ») · SIRV2 : {len(v2)}"
    )

    # 1. Par mois d'apparition
    print("\n1. Par mois d'apparition (toutes interruptions, END brut en MWh)")
    print(
        "  mois    |  nb v1 |  nb V2 | écart |   END v1 (MWh) |   END V2 (MWh) |   écart"
    )
    par_mois: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for x in hf.values():
        m = par_mois[_mois(x["apparition"])]
        m[0] += 1
        m[2] += x["end"]
    for x in v2.values():
        m = par_mois[_mois(x["apparition"])]
        m[1] += 1
        m[3] += x["end"]
    for m, (n1, n2, e1, e2) in sorted(par_mois.items()):
        print(
            f"  {m} | {n1:>6} | {n2:>6} | {n2 - n1:>+5} | {e1:>14,.3f} | {e2:>14,.3f} | {e2 - e1:>+9,.3f}"
        )

    # 2. Par mois de remise, filtres des écrans
    print(
        "\n2. Par mois de remise, filtres des écrans END (clôturées/validées, hors force majeure)"
    )
    print("  mois    |  nb v1 |  nb V2 |   END v1 (MWh) |   END V2 (MWh) |   écart")
    ecran: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for x in hf.values():
        if compte_ecran(x):
            e = ecran[_mois(x["remise"])]
            e[0] += 1
            e[2] += x["end"]
    for x in v2.values():
        if compte_ecran(x):
            e = ecran[_mois(x["remise"])]
            e[1] += 1
            e[3] += x["end"]
    for m, (n1, n2, e1, e2) in sorted(ecran.items()):
        print(
            f"  {m} | {n1:>6} | {n2:>6} | {e1:>14,.3f} | {e2:>14,.3f} | {e2 - e1:>+9,.3f}"
        )

    # 3. Par région
    print(
        "\n3. Par région sur la période (service rattaché ; v1 : même règle que la reprise)"
    )
    regions: dict[str, list[float]] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for x in hf.values():
        r = regions[
            services.get(x["service_id"], ("", "sans service"))[1]
            if x["service_id"]
            else "sans service"
        ]
        r[0] += 1
        r[2] += x["end"]
    for x in v2.values():
        r = regions[
            services.get(x["service_id"], ("", "sans service"))[1]
            if x["service_id"]
            else "sans service"
        ]
        r[1] += 1
        r[3] += x["end"]
    for nom, (n1, n2, e1, e2) in sorted(regions.items()):
        print(f"  {nom[:28]:<28} | {n1:>6} | {n2:>6} | END {e1:>12,.3f} | {e2:>12,.3f}")

    # 4. Interruption par interruption
    absentes_v2 = [k for k in hf if sir_par_legacy.get(k) not in v2]
    legacy_par_sir = {v: k for k, v in sir_par_legacy.items()}
    sans_v1 = [i for i in v2 if legacy_par_sir.get(i) not in hf]
    compteur: Counter = Counter()
    lignes_csv: list[dict[str, Any]] = []
    for cle, x in hf.items():
        sir_id = sir_par_legacy.get(cle)
        if sir_id not in v2:
            continue
        champs = ecarts_interruption(x, v2[sir_id])
        compteur.update(champs)
        if champs:
            y = v2[sir_id]
            lignes_csv.append(
                {
                    "ninterruption": cle,
                    "sirv2_id": sir_id,
                    "ecarts": " ".join(champs),
                    "apparition_v1": x["apparition"],
                    "apparition_v2": y["apparition"],
                    "remise_v1": x["remise"],
                    "remise_v2": y["remise"],
                    "end_v1": x["end"],
                    "end_v2": y["end"],
                    "puissance_v1_mw": x["puissance_mw"],
                    "puissance_v2_mw": y["puissance_mw"],
                    "fm_v1": x["force_majeure"],
                    "fm_v2": y["force_majeure"],
                    "statut_v1": x["statut"],
                    "statut_v2": y["statut"],
                    "service_v1": x["service_id"],
                    "service_v2": y["service_id"],
                }
            )
    print("\n4. Interruption par interruption")
    print(
        f"  absentes de SIRV2 : {len(absentes_v2)} · SIRV2 sans équivalent v1 sur la période : {len(sans_v1)}"
    )
    print(f"  écarts par champ : {dict(compteur) or 'aucun'}")
    if sans_v1:
        print(
            f"  SIRV2 sans équivalent (ids) : {sans_v1[:20]}{' …' if len(sans_v1) > 20 else ''}"
        )

    # 5. Unité de l'END
    def _mediane(donnees: dict[Any, dict[str, Any]]) -> tuple[float, int] | None:
        r = [
            x["end"] / (x["puissance_mw"] * x["duree_h"])
            for x in donnees.values()
            if x["end"] and x["puissance_mw"] and x["duree_h"]
        ]
        return (statistics.median(r), len(r)) if r else None

    print(
        "\n5. Unité de l'END : médiane END / (puissance MW × durée h) — 1 = MWh, 1 000 = kWh"
    )
    for nom, donnees, attendu in (
        ("SIR v1 (ENDD÷1000)", hf, "MWh"),
        ("SIRV2 (end_mwh)", v2, "MWh"),
    ):
        res = _mediane(donnees)
        if res is None:
            continue
        med, n = res
        unite = "MWh" if 0.5 < med < 2 else "kWh" if 500 < med < 2000 else "atypique"
        alerte = "  ← à corriger : backfill_end_unite.py" if unite != attendu else ""
        print(f"   {nom:<16} : {med:>10.4f} sur {n} interruptions → {unite}{alerte}")

    chemin = (
        get_settings().reports_dir
        / f"diag_interruptions_end_{args.depuis}_{args.jusqu_a}.csv"
    )
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        if lignes_csv:
            w = csv.DictWriter(f, fieldnames=list(lignes_csv[0]), delimiter=";")
            w.writeheader()
            w.writerows(lignes_csv)
    print(f"\nDétail des écarts : {chemin}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
