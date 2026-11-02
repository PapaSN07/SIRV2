#!/usr/bin/env python3
"""Sonde (lecture seule) : délégation des postes sources, départs et tronçons dans le SIG de SIR v1.

Tables HFSQL PosteSource_SIG, FEEDERS_SIG (ou Feeder_SIG) et Troncon_SIG. Délégations SENELEC :
DRS (Sud), DRN (Nord), DRCE (Centre Est), DRCO (Centre Ouest) → Régions ; délégations de Dakar
→ Dakar. But : donner une région à chaque départ (SDRBD a des départs côté Régions).

Affiche :
  - colonnes et 3 lignes de chaque table ;
  - valeurs de délégation et leur nombre ;
  - pour les départs : délégation SIG × service SIRV2 du départ (rapprochement par nom) ;
  - pour les postes sources : délégation SIG × région SIRV2 actuelle ;
  - pour les tronçons : délégations par départ (un départ sur plusieurs délégations ?).

Usage (poste ETL, réseau SENELEC) :
    python scripts/migration/probe_sig_regions.py
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402

_TABLES = {
    "postes_sources": ("PosteSource_SIG", "PostesSources_SIG", "POSTESOURCE_SIG"),
    "feeders": ("FEEDERS_SIG", "Feeder_SIG", "Feeders_SIG"),
    "troncons": ("Troncon_SIG",),
}


def cle_nom(valeur: Any) -> str:
    """Nom normalisé pour rapprocher SIG et SIRV2 (sans accents, espaces ni ponctuation)."""
    texte = (
        unicodedata.normalize("NFKD", str(valeur or ""))
        .encode("ascii", "ignore")
        .decode()
        .upper()
    )
    return re.sub(r"[^A-Z0-9]", "", texte)


def colonne(row: dict[str, Any], *mots: str) -> Any:
    for nom, valeur in row.items():
        if any(m in str(nom).lower() for m in mots):
            return valeur
    return None


def lire(conn, noms: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]]:
    for nom in noms:
        try:
            return nom, fetch_all(conn, f"SELECT * FROM {nom}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {nom} : {str(exc)[:90]}")
    return "", []


def main() -> int:
    conn = connect_hfsql()
    try:
        donnees = {cle: lire(conn, noms) for cle, noms in _TABLES.items()}
    finally:
        conn.close()

    for cle, (nom, rows) in donnees.items():
        print(f"\n=== {nom or cle} : {len(rows)} ligne(s)")
        if not rows:
            continue
        print(f"  colonnes : {list(rows[0])}")
        for r in rows[:3]:
            print(f"  {dict(list(r.items())[:14])}")
        print(
            f"  délégations : {dict(Counter(str(colonne(r, 'delegation') or '(vide)').strip() for r in rows).most_common(20))}"
        )

    with get_session() as session:
        feeders_v2 = {
            cle_nom(lib): (str(svc or "—"), str(reg or "—"))
            for lib, svc, reg in session.execute(
                text(
                    "SELECT f.libelle, s.code, r.libelle FROM dbo.feeders f LEFT JOIN dbo.services s ON s.id = f.service_id "
                    "LEFT JOIN dbo.regions r ON r.id = s.region_id"
                )
            ).all()
        }
        postes_v2 = {
            cle_nom(lib): str(reg or "—")
            for lib, reg in session.execute(
                text(
                    "SELECT p.libelle, r.libelle FROM dbo.postes_sources p LEFT JOIN dbo.regions r ON r.id = p.region_id"
                )
            ).all()
        }
        session.rollback()

    _, feeders_sig = donnees["feeders"]
    if feeders_sig:
        croisement: Counter = Counter()
        non_trouves = 0
        for r in feeders_sig:
            nom = colonne(r, "nomfeeder", "feeder", "nom")
            v2 = feeders_v2.get(cle_nom(nom))
            if v2 is None:
                non_trouves += 1
                continue
            croisement[(str(colonne(r, "delegation") or "(vide)").strip(), v2[0])] += 1
        print(
            f"\n=== Départs SIG × service SIRV2 ({non_trouves} départ(s) SIG sans équivalent par le nom)"
        )
        for (deleg, svc), n in sorted(croisement.items()):
            print(f"  {deleg:<12} | {svc:<10} | {n}")

    _, postes_sig = donnees["postes_sources"]
    if postes_sig:
        croisement = Counter()
        for r in postes_sig:
            nom = colonne(r, "nompostesource", "postesource", "nom")
            croisement[
                (
                    str(colonne(r, "delegation") or "(vide)").strip(),
                    postes_v2.get(cle_nom(nom), "absent SIRV2"),
                )
            ] += 1
        print("\n=== Postes sources SIG : délégation × région SIRV2 actuelle")
        for (deleg, reg), n in sorted(croisement.items()):
            print(f"  {deleg:<12} | {reg:<14} | {n}")

    _, troncons = donnees["troncons"]
    if troncons:
        par_depart: dict[str, set[str]] = defaultdict(set)
        for r in troncons:
            par_depart[str(colonne(r, "nomfeeder") or "").strip()].add(
                str(colonne(r, "delegation") or "").strip()
            )
        multiples = {d: sorted(v) for d, v in par_depart.items() if len(v) > 1}
        print(
            f"\n=== Tronçons : {len(par_depart)} départ(s), {len(multiples)} sur plusieurs délégations"
        )
        for depart, delegs in sorted(multiples.items())[:30]:
            svc = feeders_v2.get(cle_nom(depart), ("absent SIRV2", ""))[0]
            print(f"  {depart[:30]:<30} | {svc:<10} | {', '.join(delegs)}")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
