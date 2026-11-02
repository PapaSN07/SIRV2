#!/usr/bin/env python3
"""Supprime les interruptions de test saisies directement dans SIRV2 (hors reprise SIR v1).

Une interruption « saisie SIRV2 » est absente de la table de correspondance id_maps/interruptions :
elle n'a pas d'équivalent dans HFSQL. Avant la bascule, ce sont des essais, qui doubleraient les
vraies coupures reprises de SIR v1 et fausseraient SAIFI/SAIDI.

La simulation (par défaut) liste les interruptions visées. --execute les supprime avec ce qui
en dépend (postes coupés, END, étapes, historique des statuts — suppression en cascade) ; les
conversations de l'assistant qui les citent sont conservées, sans le lien.

Usage :
    python scripts/migration/supprimer_saisies_test.py --depuis 2026-06-01
    python scripts/migration/supprimer_saisies_test.py --depuis 2026-06-01 --execute
    python scripts/migration/supprimer_saisies_test.py --depuis 2026-06-01 --ids 81234 81240 --execute
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import bindparam, text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.id_maps import IdMapStore  # noqa: E402

_LISTE = text(
    "SELECT i.id, i.numero_interruption, i.type_direction, i.statut, i.date_apparition, "
    "s.libelle AS service, u.login AS saisi_par "
    "FROM dbo.interruptions i "
    "LEFT JOIN dbo.services s ON s.id = i.service_id "
    "LEFT JOIN dbo.utilisateurs u ON u.id = i.created_by_id "
    "WHERE i.date_apparition >= :depuis ORDER BY i.date_apparition"
)


def a_supprimer(rows: list, migrees: set[int], ids: set[int] | None) -> list:
    """Interruptions sans équivalent SIR v1, éventuellement restreintes à une liste d'ids."""
    return [
        r
        for r in rows
        if int(r.id) not in migrees and (ids is None or int(r.id) in ids)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--depuis", required=True, type=lambda s: datetime.strptime(s, "%Y-%m-%d")
    )
    parser.add_argument(
        "--ids", type=int, nargs="*", help="Restreindre à ces identifiants SIRV2"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Supprimer (sinon simulation)"
    )
    args = parser.parse_args()

    migrees = {int(v) for v in IdMapStore().load("interruptions").values()}
    if not migrees:
        print(
            "Table de correspondance id_maps/interruptions vide : arrêt (tout paraîtrait saisi dans SIRV2)."
        )
        return 1
    with get_session() as session:
        rows = session.execute(_LISTE, {"depuis": args.depuis}).all()
        cibles = a_supprimer(rows, migrees, set(args.ids) if args.ids else None)
        print(
            f"{len(cibles)} interruption(s) saisie(s) dans SIRV2 depuis le {args.depuis:%d/%m/%Y} :"
        )
        for r in cibles:
            print(
                f"  id {r.id} · n° {r.numero_interruption} · {r.type_direction} · {r.statut} · "
                f"{r.date_apparition:%d/%m/%Y %H:%M} · {r.service or '—'} · saisie par {r.saisi_par or '—'}"
            )
        if not cibles or not args.execute:
            session.rollback()
            if cibles:
                print("\nSimulation : rien n'a été supprimé. Relancer avec --execute.")
            return 0
        ids = [int(r.id) for r in cibles]
        session.execute(
            text(
                "UPDATE dbo.assistant_conversations SET interruption_id = NULL WHERE interruption_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids},
        )
        supprimees = session.execute(
            text("DELETE FROM dbo.interruptions WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": ids},
        ).rowcount
    print(f"\n{supprimees} interruption(s) supprimée(s).")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
