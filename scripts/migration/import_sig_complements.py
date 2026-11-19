#!/usr/bin/env python3
"""Reprise complémentaire du SIG de SIR v1 (srv-hfsql) vers SIRV2.

1. Postes sources du SIG (PosteSource_SIG) → dbo.postes_sources_sig
2. Départs du SIG (FEEDERS_SIG, ou Feeder_SIG) → dbo.feeders_sig, rattachés au feeder SIRV2 de même nom
3. Colonnes complémentaires des nœuds (DELEGATION, REGION, PUISSANCE_, FAMILLE_PO, CELLULE) et des
   tronçons (IMATFEEDER, SECTIONS, SS, TYPE_CONDU, DELEGATION, DATE_MAJ) déjà importés.

Les colonnes des deux premières tables ne sont pas connues d'avance : le nom, le code, le poste source,
la délégation… sont reconnus par leur nom de colonne ; toutes les colonnes sont gardées dans
``attributs`` (JSON) et affichées dans Administration → SIG.

Usage (poste ETL SENELEC, accès srv-hfsql) :
    python scripts/migration/import_sig_complements.py            # simulation : rien n'est écrit
    python scripts/migration/import_sig_complements.py --execute  # écrit (sauvegarder la base avant)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import text  # noqa: E402

from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_all  # noqa: E402
from scripts.migration.loaders.sig import attributs_noeud, attributs_troncon  # noqa: E402
from scripts.migration.transforms.rows import row_get  # noqa: E402

TABLES_POSTES = ("PosteSource_SIG", "PostesSources_SIG", "POSTESOURCE_SIG", "PosteSources_SIG")
TABLES_FEEDERS = ("FEEDERS_SIG", "Feeder_SIG", "Feeders_SIG", "FEEDER_SIG")
LOT = 1000


def cle_nom(valeur: Any) -> str:
    texte = unicodedata.normalize("NFKD", str(valeur or "")).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]", "", texte)


def _colonne(row: dict[str, Any], *motifs: str, exclure: tuple[str, ...] = ()) -> Any:
    """Valeur de la première colonne dont le nom contient l'un des motifs (ordre des motifs)."""
    noms = {str(k).lower(): k for k in row}
    for motif in motifs:
        for bas, original in noms.items():
            if motif in bas and not any(e in bas for e in exclure):
                valeur = row[original]
                if valeur not in (None, ""):
                    return valeur
    return None


def _texte(valeur: Any, longueur: int) -> str | None:
    if valeur is None:
        return None
    texte = str(valeur).strip()
    return texte[:longueur] if texte else None


def _nombre(valeur: Any) -> float | None:
    try:
        return float(str(valeur).replace(",", ".")) if valeur not in (None, "") else None
    except ValueError:
        return None


def _json(row: dict[str, Any]) -> str:
    def conv(v: Any) -> Any:
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, (bytes, bytearray)):
            return None
        return v

    return json.dumps({str(k): conv(v) for k, v in row.items() if conv(v) not in (None, "")}, ensure_ascii=False, default=str)


def _identifiant(row: dict[str, Any], index: int) -> str:
    valeur = _colonne(row, "id", "fid", "objectid", exclure=("idtype", "idreg", "iddeleg"))
    return str(valeur).strip() if valeur not in (None, "") else f"ligne-{index}"


def poste_source_sig(row: dict[str, Any], index: int) -> dict[str, Any]:
    """Ligne de PosteSource_SIG → colonnes de dbo.postes_sources_sig."""
    return {
        "legacy_id": _identifiant(row, index)[:100],
        "nom": _texte(_colonne(row, "nompostesource", "nom_poste", "nomposte", "libelle", "nom", "sstation", "station"), 255),
        "code": _texte(_colonne(row, "code", "imat", "matricule", "sigle"), 100),
        "delegation": _texte(_colonne(row, "delegation"), 100),
        "region": _texte(_colonne(row, "region"), 100),
        "tension": _texte(_colonne(row, "tension"), 50),
        "coord_x": _nombre(_colonne(row, "corx", "coord_x", "coordx", "x_")),
        "coord_y": _nombre(_colonne(row, "cory", "coord_y", "coordy", "y_")),
        "attributs": _json(row),
    }


def feeder_sig(row: dict[str, Any], index: int) -> dict[str, Any]:
    """Ligne de FEEDERS_SIG → colonnes de dbo.feeders_sig."""
    return {
        "legacy_id": _identifiant(row, index)[:100],
        "nom": _texte(_colonne(row, "nomfeeder", "nom_feeder", "feeder", "libelle", "nom", exclure=("imat",)), 255),
        "code": _texte(_colonne(row, "imatfeeder", "imat", "code", "matricule"), 100),
        "poste_source": _texte(_colonne(row, "postesource", "poste_source", "sstation", "station", "ss"), 255),
        "delegation": _texte(_colonne(row, "delegation"), 100),
        "tension": _texte(_colonne(row, "tension"), 50),
        "attributs": _json(row),
    }


def _lire(conn, noms: tuple[str, ...]) -> tuple[str, list[dict[str, Any]]]:
    for nom in noms:
        try:
            return nom, fetch_all(conn, f"SELECT * FROM {nom}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {nom} : {str(exc)[:90]}")
    return "", []


def _upsert(session, table: str, lignes: list[dict[str, Any]]) -> tuple[int, int]:
    existants = {r[0] for r in session.execute(text(f"SELECT legacy_id FROM dbo.{table}")).all()}
    nouveaux = [l for l in lignes if l["legacy_id"] not in existants]
    maj = [l for l in lignes if l["legacy_id"] in existants]
    if nouveaux:
        colonnes = list(nouveaux[0])
        sql = text(f"INSERT INTO dbo.{table} ({', '.join(colonnes)}) VALUES ({', '.join(':' + c for c in colonnes)})")
        for i in range(0, len(nouveaux), LOT):
            session.execute(sql, nouveaux[i : i + LOT])
    if maj:
        colonnes = [c for c in maj[0] if c != "legacy_id"]
        sql = text(f"UPDATE dbo.{table} SET {', '.join(f'{c} = :{c}' for c in colonnes)} WHERE legacy_id = :legacy_id")
        for i in range(0, len(maj), LOT):
            session.execute(sql, maj[i : i + LOT])
    return len(nouveaux), len(maj)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="écrire dans SIRV2 (sinon simulation)")
    args = parser.parse_args()

    conn = connect_hfsql()
    try:
        nom_ps, postes_rows = _lire(conn, TABLES_POSTES)
        nom_fd, feeders_rows = _lire(conn, TABLES_FEEDERS)
        noeuds_rows = fetch_all(conn, "SELECT IDNoeud_SIG, DELEGATION, REGION, PUISSANCE_, FAMILLE_PO, CELLULE FROM Noeud_SIG")
        troncons_rows = fetch_all(
            conn, "SELECT ID_Troncon_SIG, IMATFEEDER, SECTIONS, SS, TYPE_CONDU, DELEGATION, DATE_MAJ FROM Troncon_SIG"
        )
    finally:
        conn.close()

    postes = [poste_source_sig(r, i) for i, r in enumerate(postes_rows, 1)]
    feeders = [feeder_sig(r, i) for i, r in enumerate(feeders_rows, 1)]
    for nom, rows, lignes in ((nom_ps, postes_rows, postes), (nom_fd, feeders_rows, feeders)):
        print(f"\n=== {nom or '(table introuvable)'} : {len(rows)} ligne(s)")
        if rows:
            print(f"  colonnes HFSQL : {list(rows[0])}")
            for l in lignes[:3]:
                print(f"  → {({k: v for k, v in l.items() if k != 'attributs'})}")
            sans_nom = sum(1 for l in lignes if not l["nom"])
            print(f"  sans nom reconnu : {sans_nom}")

    with get_session() as session:
        feeders_v2: dict[str, int] = {}
        for fid, libelle, code in session.execute(text("SELECT id, libelle, code FROM dbo.feeders")).all():
            for k in {cle_nom(libelle), cle_nom(code)}:
                if k:
                    feeders_v2.setdefault(k, int(fid))
        for l in feeders:
            l["feeder_id"] = feeders_v2.get(cle_nom(l["nom"])) or feeders_v2.get(cle_nom(l["code"]))
        rattaches = sum(1 for l in feeders if l["feeder_id"])
        print(f"\nDéparts SIG rattachés à un feeder SIRV2 par le nom : {rattaches} / {len(feeders)}")

        noeuds = [{"legacy_id": int(row_get(r, "IDNoeud_SIG", "idnoeud_sig")), **attributs_noeud(r)} for r in noeuds_rows if row_get(r, "IDNoeud_SIG", "idnoeud_sig") is not None]
        troncons = [
            {"legacy_id": int(row_get(r, "ID_Troncon_SIG", "id_troncon_sig")), **attributs_troncon(r)}
            for r in troncons_rows
            if row_get(r, "ID_Troncon_SIG", "id_troncon_sig") is not None
        ]
        print(f"Nœuds à compléter : {len(noeuds)} ; tronçons à compléter : {len(troncons)}")
        print(f"  exemple nœud : {noeuds[:1]}")
        print(f"  exemple tronçon : {troncons[:1]}")

        if not args.execute:
            print("\nSimulation : rien n'est écrit. Relancer avec --execute (après sauvegarde de la base).")
            session.rollback()
            return 0

        if postes:
            print("postes_sources_sig (ajoutés, mis à jour) :", _upsert(session, "postes_sources_sig", postes))
        if feeders:
            print("feeders_sig (ajoutés, mis à jour) :", _upsert(session, "feeders_sig", feeders))
        sql_n = text(
            "UPDATE dbo.noeuds_sig SET delegation = :delegation, region = :region, puissance = :puissance, "
            "famille_poste = :famille_poste, cellule = :cellule WHERE legacy_id = :legacy_id"
        )
        for i in range(0, len(noeuds), LOT):
            session.execute(sql_n, noeuds[i : i + LOT])
        sql_t = text(
            "UPDATE dbo.troncons_sig SET imat_feeder = :imat_feeder, section = :section, poste_source = :poste_source, "
            "type_conducteur = :type_conducteur, delegation = :delegation, date_maj = :date_maj WHERE legacy_id = :legacy_id"
        )
        for i in range(0, len(troncons), LOT):
            session.execute(sql_t, troncons[i : i + LOT])
        session.commit()
        print("Écrit : nœuds et tronçons complétés.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
