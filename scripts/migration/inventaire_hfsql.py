#!/usr/bin/env python3
"""Inventaire de la base SIR v1 (HFSQL) : lignes et dernière date d'activité de chaque table.

Sert à vérifier que tout ce que l'ancien SIR utilise encore est repris dans SIRV2 :
une table avec des lignes récentes correspond à un processus vivant.

Les tables viennent de SIR.sql (racine du dépôt) ; pour chaque table, le script compte les
lignes et cherche la date la plus récente dans ses colonnes DATE/DATETIME. Lecture seule.

Usage (poste ETL avec le pilote ODBC HFSQL, réseau SENELEC) :
    python scripts/migration/inventaire_hfsql.py
Rapport : scripts/migration/reports/inventaire_hfsql.json (+ .csv)
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402

from scripts.migration.config import ensure_dirs, get_settings  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql  # noqa: E402

_TYPES_DATE = ("DATETIME", "DATE ", "DATE,", "TIMESTAMP")


def tables_sir_sql(chemin: Path) -> dict[str, list[str]]:
    """Tables de SIR.sql et leurs colonnes date."""
    texte = chemin.read_text(encoding="latin-1")
    tables: dict[str, list[str]] = {}
    for nom, corps in re.findall(r"CREATE TABLE \[([^\]]+)\] \((.*?)\);", texte, re.S):
        dates = []
        for ligne in corps.splitlines():
            m = re.match(r"\s*\[([^\]]+)\]\s+(\w+)", ligne)
            if m and any((m.group(2).upper() + " ").startswith(t.strip(" ,")) for t in _TYPES_DATE):
                dates.append(m.group(1))
        # les colonnes « Heure… » ne portent que l'heure : inutiles pour dater l'activité
        dates = [d for d in dates if not d.lower().startswith("heure")]
        prioritaires = [d for d in dates if re.search(r"saisie|creation|enregistrement|envoi|apparition", d, re.I)]
        tables[nom] = (prioritaires or dates)[:3]
    return tables


def _scalaire(cur, sql: str) -> Any:
    cur.execute(sql)
    row = cur.fetchone()
    return row[0] if row else None


def inventorier(conn, tables: dict[str, list[str]]) -> list[dict[str, Any]]:
    resultats = []
    cur = conn.cursor()
    for nom, dates in tables.items():
        ligne: dict[str, Any] = {"table": nom, "lignes": None, "derniere_date": None, "colonne_date": None, "erreur": None}
        nom_sql = nom.split(".")[-1]
        for forme in (nom_sql, f'"{nom_sql}"'):
            try:
                ligne["lignes"] = int(_scalaire(cur, f"SELECT COUNT(*) FROM {forme}") or 0)
                ligne["erreur"] = None
                nom_sql = forme
                break
            except Exception as exc:  # noqa: BLE001 — table absente ou nom non standard
                ligne["erreur"] = str(exc)[:160]
        if ligne["lignes"]:
            for col in dates:
                try:
                    valeur = _scalaire(cur, f"SELECT MAX({col}) FROM {nom_sql}")
                except Exception:  # noqa: BLE001
                    continue
                if valeur and (ligne["derniere_date"] is None or str(valeur) > ligne["derniere_date"]):
                    ligne["derniere_date"], ligne["colonne_date"] = str(valeur)[:19], col
        resultats.append(ligne)
        etat = ligne["erreur"] or f"{ligne['lignes']:>9} ligne(s)  {ligne['derniere_date'] or ''}"
        print(f"  {nom:<40} {etat}")
    return resultats


def main() -> int:
    ensure_dirs()
    settings = get_settings()
    tables = tables_sir_sql(_ROOT / "SIR.sql")
    print(f"Source : {settings.hfsql_server} / {settings.hfsql_database} — {len(tables)} tables (SIR.sql)\n")
    conn = connect_hfsql()
    try:
        resultats = inventorier(conn, tables)
    finally:
        conn.close()
    rapport = settings.reports_dir / "inventaire_hfsql.json"
    rapport.write_text(json.dumps(resultats, indent=2, ensure_ascii=False), encoding="utf-8")
    with (settings.reports_dir / "inventaire_hfsql.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(resultats[0]), delimiter=";")
        w.writeheader()
        w.writerows(resultats)
    vides = sum(1 for r in resultats if not r["lignes"])
    print(f"\n{len(resultats)} tables, {vides} vides ou illisibles. Rapport : {rapport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
