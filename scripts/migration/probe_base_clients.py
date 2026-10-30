#!/usr/bin/env python3
"""Sonde de la base clients (lecture seule) : SSIS BI_ODS et tables SIR v1 du lien poste ↔ UR.

Objectif : préparer la reprise dans SIRV2 du calcul du nombre de clients (atelier SAIFI/SAIDI
de l'application bureau SIR) :
  - BI_ODS.dbo.CONTRATS_PAR_AGENCE_UR (SRV-ASREPORTS), alimentée par SSIS chaque mois,
    équivalent du fichier « nombredeclientsh2mc_MMAAAA.xlsx » chargé par l'ancien SIR ;
  - SIR v1 (HFSQL) : PosteClient (poste ↔ unité de relève), ReferenceClient, NombreClientMois.

Affiche les colonnes, quelques lignes, les périodes disponibles et les totaux de contrats,
pour vérifier la clé commune (code de l'unité de relève, ex. 1100200I).

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_base_clients.py
    python scripts/migration/probe_base_clients.py --serveur SRV-ASREPORTS --base BI_ODS
Connexion BI_ODS : authentification Windows (Trusted_Connection) sauf si BI_ODS_USER / BI_ODS_PASSWORD
sont définis dans l'environnement.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402

from scripts.migration.hfsql_odbc import connect_hfsql  # noqa: E402

TABLE_BI = "CONTRATS_PAR_AGENCE_UR"


def _afficher(cur, titre: str, sql: str, limite: int = 8) -> None:
    print(f"\n--- {titre}")
    try:
        cur.execute(sql)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERREUR : {str(exc)[:300]}")
        return
    colonnes = [c[0] for c in cur.description]
    print("  " + " | ".join(colonnes))
    for row in cur.fetchmany(limite):
        print("  " + " | ".join("" if v is None else str(v) for v in row))


def sonder_bi(serveur: str, base: str) -> None:
    import pyodbc

    pilotes = [p for p in pyodbc.drivers() if "SQL Server" in p]
    pilote = next((p for p in pilotes if "18" in p), pilotes[-1] if pilotes else "ODBC Driver 17 for SQL Server")
    auth = (
        f"UID={os.environ['BI_ODS_USER']};PWD={os.environ['BI_ODS_PASSWORD']};"
        if os.environ.get("BI_ODS_USER")
        else "Trusted_Connection=yes;"
    )
    print(f"=== BI_ODS : {serveur} / {base} (pilote {pilote})")
    try:
        conn = pyodbc.connect(
            f"DRIVER={{{pilote}}};SERVER={serveur};DATABASE={base};{auth}TrustServerCertificate=yes;", timeout=30
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  Connexion impossible : {str(exc)[:300]}")
        return
    cur = conn.cursor()
    _afficher(
        cur,
        "Colonnes",
        "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME = '{TABLE_BI}' ORDER BY ORDINAL_POSITION",
        50,
    )
    _afficher(cur, "Exemple", f"SELECT TOP 8 * FROM dbo.{TABLE_BI}")
    _afficher(cur, "Volume", f"SELECT COUNT(*) AS lignes FROM dbo.{TABLE_BI}")
    # Colonnes de période et de nombre, devinées d'après les noms
    cur.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION", TABLE_BI
    )
    cols = [r[0] for r in cur.fetchall()]
    periode = [c for c in cols if any(k in c.lower() for k in ("date", "periode", "mois", "annee", "year", "month"))]
    nombre = [c for c in cols if any(k in c.lower() for k in ("nombre", "nb", "contrat", "count"))]
    if periode and nombre:
        grp = ", ".join(periode[:2])
        _afficher(
            cur,
            f"Contrats par période ({grp} · somme de {nombre[-1]})",
            f"SELECT TOP 24 {grp}, SUM(CAST({nombre[-1]} AS BIGINT)) AS contrats, COUNT(*) AS lignes "
            f"FROM dbo.{TABLE_BI} GROUP BY {grp} ORDER BY {grp} DESC",
            24,
        )
    conn.close()


def sonder_hfsql() -> None:
    print("\n=== SIR v1 (HFSQL)")
    conn = connect_hfsql()
    cur = conn.cursor()
    _afficher(cur, "PosteClient (lien poste ↔ UR)", "SELECT TOP 8 * FROM PosteClient")
    _afficher(cur, "ReferenceClient (clients par UR)", "SELECT TOP 8 * FROM ReferenceClient")
    _afficher(cur, "NombreClientMois (12 derniers)", "SELECT TOP 12 * FROM NombreClientMois ORDER BY Annee DESC, MoisNumerique DESC")
    _afficher(
        cur,
        "PosteClient : postes et UR distincts",
        "SELECT COUNT(DISTINCT IDPostes) AS postes, COUNT(DISTINCT Codereference) AS ur, SUM(Nombreclient) AS clients FROM PosteClient",
    )
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serveur", default="SRV-ASREPORTS")
    parser.add_argument("--base", default="BI_ODS")
    args = parser.parse_args()
    sonder_bi(args.serveur, args.base)
    sonder_hfsql()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
