#!/usr/bin/env python3
"""Reprise des données SIR v1 d'une période récente (ex. juin 2026 → aujourd'hui) dans SIRV2.

SIR v1 (HFSQL) reste en exploitation pendant la préparation de la bascule : SIRV2 doit rattraper
les interruptions saisies depuis la dernière migration, leurs postes coupés, l'END et la base
clients, puis recalculer SAIFI/SAIDI.

Sans --execute : état comparé HFSQL / SIRV2 par mois et plan des étapes, rien n'est écrit.
Avec --execute : les étapes s'enchaînent et s'arrêtent à la première erreur ; relancer avec
--a-partir-de <étape> pour reprendre. Chaque étape est relançable (les lignes déjà reprises
sont reconnues par les tables de correspondance id_maps).

Étapes :
  interruptions  extraction HFSQL (distribution, historique, transport, OMVG, END) + ETL
                 (nouvelles lignes et mise à jour des lignes déjà reprises : statut, clôture…)
                 + backfill des clés étrangères ;
  durees         durées en heures (colonne dureeHeure, règle du 28/10) ;
  postes         postes coupés (IndicateursTransportDistribution.PosteInterruption) + contexte ;
  clients        nombre de clients par mois (NombreClientMois) jusqu'au mois précédant le premier
                 mois chargé par la base clients BI_ODS (les mois suivants viennent de BI_ODS) ;
  sms            historique des SMS envoyés.
Puis, dans le conteneur : recalcul SAIFI/SAIDI (commande affichée à la fin).

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/delta_periode.py --depuis 2026-06-01             # état + plan
    python scripts/migration/delta_periode.py --depuis 2026-06-01 --execute
    python scripts/migration/delta_periode.py --depuis 2026-06-01 --execute --a-partir-de postes
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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
from scripts.migration.hfsql_odbc import connect_hfsql  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402
from scripts.migration.transforms.dates import resolve_interruption_date_apparition  # noqa: E402

ETAPES = ("interruptions", "durees", "postes", "clients", "sms")
TABLES_HFSQL = {
    "Interruptions": "distribution",
    "Interruptions_Histo": "distribution (historique)",
    "InterruptionsTransport": "transport",
    "Interruptions_OMVG": "omvg",
}
_SCRIPTS = _ROOT / "scripts" / "migration"


def _mois(d: datetime) -> str:
    return f"{d.year}-{d.month:02d}"


# ── État ─────────────────────────────────────────────────────────────────────


def etat_hfsql(depuis: datetime) -> dict[str, Counter]:
    """Interruptions SIR v1 par mois d'apparition (lecture des seules colonnes de date)."""
    resultat: dict[str, Counter] = {}
    conn = connect_hfsql()
    try:
        for table in TABLES_HFSQL:
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT DateApparition, heureApparition FROM {table}")
            except Exception as exc:  # noqa: BLE001
                print(f"  {table} : lecture impossible ({str(exc)[:120]})")
                continue
            colonnes = [c[0] for c in cur.description]
            compte: Counter = Counter()
            for row in cur.fetchall():
                date_app = resolve_interruption_date_apparition(
                    dict(zip(colonnes, row))
                )
                if date_app is not None and date_app >= depuis:
                    compte[_mois(date_app)] += 1
            resultat[table] = compte
    finally:
        conn.close()
    return resultat


def etat_sirv2(session, depuis: datetime) -> dict[str, Any]:
    migrees = {int(v) for v in IdMapStore().load("interruptions").values()}
    interruptions: dict[str, Counter] = defaultdict(Counter)
    for ident, type_direction, date_app in session.execute(
        text(
            "SELECT id, type_direction, date_apparition FROM dbo.interruptions WHERE date_apparition >= :d"
        ),
        {"d": depuis},
    ).all():
        origine = "reprises" if int(ident) in migrees else "saisies SIRV2"
        interruptions[_mois(date_app)][f"{type_direction} {origine}"] += 1
    postes = dict(
        session.execute(
            text(
                "SELECT FORMAT(i.date_apparition, 'yyyy-MM'), COUNT(DISTINCT pi.interruption_id) "
                "FROM dbo.poste_interruptions pi JOIN dbo.interruptions i ON i.id = pi.interruption_id "
                "WHERE i.date_apparition >= :d GROUP BY FORMAT(i.date_apparition, 'yyyy-MM')"
            ),
            {"d": depuis},
        ).all()
    )
    clients = {
        f"{a}-{m:02d}": int(n)
        for a, m, n in session.execute(
            text(
                "SELECT annee, mois, SUM(CAST(nombre_clients AS BIGINT)) FROM dbo.nombre_client_mois "
                "WHERE annee * 100 + mois >= :p GROUP BY annee, mois"
            ),
            {"p": depuis.year * 100 + depuis.month},
        ).all()
    }
    base_clients = sorted(
        f"{a}-{m:02d}"
        for a, m in session.execute(
            text("SELECT DISTINCT annee, mois FROM dbo.contrats_unites_releve")
        ).all()
    )
    return {
        "interruptions": interruptions,
        "postes": postes,
        "clients": clients,
        "base_clients": base_clients,
    }


def afficher_etat(
    depuis: datetime, hfsql: dict[str, Counter], sirv2: dict[str, Any]
) -> None:
    mois = sorted(
        {m for c in hfsql.values() for m in c}
        | set(sirv2["interruptions"])
        | set(sirv2["clients"])
    )
    print(f"\n=== État depuis le {depuis:%d/%m/%Y}")
    entete = [
        "mois",
        "v1 distrib.",
        "v1 histo",
        "v1 transport",
        "v1 OMVG",
        "SIRV2 (détail)",
        "avec postes",
        "clients",
    ]
    print("  " + " | ".join(entete))
    for m in mois:
        detail = (
            ", ".join(
                f"{k} {n}" for k, n in sorted(sirv2["interruptions"].get(m, {}).items())
            )
            or "—"
        )
        clients = sirv2["clients"].get(m)
        print(
            "  "
            + " | ".join(
                [
                    m,
                    str(hfsql.get("Interruptions", Counter())[m]),
                    str(hfsql.get("Interruptions_Histo", Counter())[m]),
                    str(hfsql.get("InterruptionsTransport", Counter())[m]),
                    str(hfsql.get("Interruptions_OMVG", Counter())[m]),
                    detail,
                    str(sirv2["postes"].get(m, 0)),
                    f"{clients:,}".replace(",", " ") if clients else "—",
                ]
            )
        )
    print(
        f"  Base clients BI_ODS chargée pour : {', '.join(sirv2['base_clients']) or 'aucun mois'}"
    )


def dernier_mois_hfsql_clients(base_clients: list[str]) -> str | None:
    """Mois précédant le premier mois de la base clients BI_ODS (AAAA-MM), ou None si aucun."""
    if not base_clients:
        return None
    annee, mois = (int(x) for x in base_clients[0].split("-"))
    annee, mois = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
    return f"{annee}-{mois:02d}"


# ── Étapes ───────────────────────────────────────────────────────────────────


def commandes(
    depuis: datetime, jusqu_a_clients: str | None
) -> dict[str, list[list[str]]]:
    jour = depuis.strftime("%Y-%m-%d")
    clients = [
        "import_nombre_client_mois.py",
        "--execute",
        "--depuis",
        str(depuis.year),
    ]
    if jusqu_a_clients:
        clients += ["--jusqu-a", jusqu_a_clients]
    return {
        "interruptions": [
            [
                "sync_interruptions.py",
                "--execute",
                "--update-existing",
                "--avec-transport",
            ]
        ],
        "durees": [
            [
                "backfill_duree_interruptions.py",
                "--execute",
                "--depuis",
                str(depuis.year),
            ]
        ],
        "postes": [
            [
                "import_poste_interruptions_itd.py",
                "--execute",
                "--resume",
                "--depuis",
                jour,
            ],
            ["backfill_poste_interruptions_context.py", "--execute"],
        ],
        "clients": [clients],
        "sms": [
            ["import_sms_historique.py", "--execute", "--depuis", str(depuis.year)]
        ],
    }


def executer(etape: str, cmds: list[list[str]], env: dict[str, str]) -> None:
    for cmd in cmds:
        print(f"\n--- [{etape}] python scripts/migration/{' '.join(cmd)}", flush=True)
        debut = time.monotonic()
        proc = subprocess.run(
            [sys.executable, str(_SCRIPTS / cmd[0]), *cmd[1:]], cwd=str(_ROOT), env=env
        )
        print(
            f"--- [{etape}] terminé en {time.monotonic() - debut:.0f} s (code {proc.returncode})",
            flush=True,
        )
        if proc.returncode != 0:
            raise SystemExit(
                f"Échec de l'étape « {etape} ». Corriger puis relancer avec --execute --a-partir-de {etape}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--depuis",
        required=True,
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        help="AAAA-MM-JJ",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Lancer les étapes (sinon état et plan)"
    )
    parser.add_argument(
        "--a-partir-de",
        choices=ETAPES,
        default=ETAPES[0],
        help="Reprendre à cette étape",
    )
    parser.add_argument(
        "--sans", choices=ETAPES, action="append", default=[], help="Sauter une étape"
    )
    args = parser.parse_args()

    # Fenêtre lue par l'extraction et l'ETL des interruptions (scripts lancés en sous-processus)
    env = {
        **os.environ,
        "MIGRATION_DATE_FROM": args.depuis.strftime("%Y-%m-%d"),
        "MIGRATION_DATE_TO": datetime.now().strftime("%Y-%m-%d"),
        "MIGRATION_DRY_RUN": "false",
    }
    os.environ.update({k: env[k] for k in ("MIGRATION_DATE_FROM", "MIGRATION_DATE_TO")})
    get_settings.cache_clear()
    ensure_dirs()
    settings = get_settings()
    print(f"HFSQL : {settings.hfsql_server} / {settings.hfsql_database}")

    hfsql = etat_hfsql(args.depuis)
    with get_session() as session:
        sirv2 = etat_sirv2(session, args.depuis)
    afficher_etat(args.depuis, hfsql, sirv2)

    jusqu_a = dernier_mois_hfsql_clients(sirv2["base_clients"])
    plan = commandes(args.depuis, jusqu_a)
    a_lancer = [
        e for e in ETAPES[ETAPES.index(args.a_partir_de) :] if e not in args.sans
    ]
    print("\n=== Plan")
    for etape in a_lancer:
        for cmd in plan[etape]:
            print(f"  [{etape}] python scripts/migration/{' '.join(cmd)}")
    print(
        f"  puis : .\\dcs exec api python -m scripts.recalcul_saifi_saidi --depuis {_mois(args.depuis)}"
    )

    rapport = (
        settings.reports_dir / f"delta_periode_{datetime.now():%Y%m%d_%H%M%S}.json"
    )
    rapport.write_text(
        json.dumps(
            {
                "depuis": args.depuis.isoformat(),
                "hfsql": hfsql,
                "sirv2": sirv2,
                "plan": a_lancer,
                "execute": args.execute,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    if not args.execute:
        print(
            f"\nSimulation : rien n'a été écrit (rapport {rapport.name}). Relancer avec --execute."
        )
        return 0

    for etape in a_lancer:
        executer(etape, plan[etape], env)

    with get_session() as session:
        afficher_etat(
            args.depuis, etat_hfsql(args.depuis), etat_sirv2(session, args.depuis)
        )
    print(
        "\nReste à recalculer SAIFI/SAIDI dans le conteneur :\n"
        f"  .\\dcs exec api python -m scripts.recalcul_saifi_saidi --depuis {_mois(args.depuis)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
