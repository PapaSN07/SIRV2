#!/usr/bin/env python3
"""Sonde (lecture seule) : textes des SMS envoyés par SIR v1, pour concevoir la saisie automatique.

But : lire un SMS au moment de son envoi depuis SIRV2 et pré-remplir la saisie de l'interruption
(départ, poste source, heure d'apparition ou de remise, cause…). Il faut d'abord connaître le
format réel des messages.

Lit smsenvoye (SIR v1) depuis --depuis, regroupe les envois du même message à plusieurs
destinataires (un message = même date à la minute, même expéditeur, même texte) et écrit :
  - reports/probe_sms_manuels.csv : un message par ligne (date, expéditeur, NInterruption, texte) ;
  - à l'écran : volumes, premiers mots les plus fréquents, et des exemples de messages
    manuels (NInterruption = 0) et liés à une interruption (NInterruption > 0).

Les messages liés à une interruption servent de vérité terrain : le texte et la fiche
correspondent, on pourra mesurer le taux de bonne lecture.

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_sms_manuels.py
    python scripts/migration/probe_sms_manuels.py --depuis 2025 --exemples 40
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql  # noqa: E402
from scripts.migration.import_repertoire_sms import champ  # noqa: E402
from scripts.migration.import_sms_historique import _date, _entier, lire_sms  # noqa: E402


def regrouper(rows: list[dict[str, Any]], depuis: int) -> list[dict[str, Any]]:
    """Un message par (minute, expéditeur, texte) : les envois à N destinataires comptent une fois."""
    messages: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        quand = _date(champ(row, "dateEnvoi"))
        texte = " ".join((champ(row, "messageenvoye") or "").split())
        if quand is None or quand.year < depuis or not texte:
            continue
        cle = (quand.strftime("%Y-%m-%d %H:%M"), champ(row, "Login"), texte)
        if cle not in messages:
            messages[cle] = {
                "date": cle[0],
                "login": cle[1],
                "interruption": _entier(champ(row, "NInterruption")),
                "exploitation": champ(row, "exploitation"),
                "destinataires": 0,
                "texte": texte,
            }
        messages[cle]["destinataires"] += 1
    return sorted(messages.values(), key=lambda m: m["date"])


def debut(texte: str, mots: int = 3) -> str:
    """Premiers mots en majuscules, chiffres remplacés par #, pour repérer les gabarits."""
    return re.sub(r"\d+", "#", " ".join(texte.upper().split()[:mots]))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--depuis", type=int, default=2026, help="Première année lue")
    parser.add_argument(
        "--exemples", type=int, default=25, help="Exemples affichés par catégorie"
    )
    args = parser.parse_args()
    ensure_dirs()

    conn = connect_hfsql()
    try:
        rows = lire_sms(conn, args.depuis)
    finally:
        conn.close()
    messages = regrouper(rows, args.depuis)
    manuels = [m for m in messages if not m["interruption"]]
    lies = [m for m in messages if m["interruption"]]
    print(
        f"{len(rows)} envoi(s) lus · {len(messages)} message(s) distinct(s) : "
        f"{len(manuels)} manuel(s), {len(lies)} lié(s) à une interruption"
    )

    for titre, lot in (("manuels", manuels), ("liés à une interruption", lies)):
        if not lot:
            continue
        print(f"\n=== Messages {titre} : débuts les plus fréquents")
        for gabarit, n in Counter(debut(m["texte"]) for m in lot).most_common(15):
            print(f"  {n:>6} | {gabarit}")
        longueurs = sorted(len(m["texte"]) for m in lot)
        print(
            f"  longueur : médiane {longueurs[len(longueurs) // 2]} car., max {longueurs[-1]}"
        )
        print(f"\n=== Exemples de messages {titre}")
        random.seed(1)
        for m in random.sample(lot, min(args.exemples, len(lot))):
            ref = f"N°{m['interruption']}" if m["interruption"] else "manuel"
            print(f"  {m['date']} | {m['login'][:10]:<10} | {ref:<10} | {m['texte']}")

    chemin = get_settings().reports_dir / "probe_sms_manuels.csv"
    with chemin.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "login",
                "interruption",
                "exploitation",
                "destinataires",
                "texte",
            ],
            delimiter=";",
        )
        w.writeheader()
        w.writerows(messages)
    print(f"\nTous les messages : {chemin}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
