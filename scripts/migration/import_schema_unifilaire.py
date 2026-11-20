#!/usr/bin/env python3
"""Import d'un schéma unifilaire (PDF AutoCAD) dans SIRV2 : postes cliquables, graphe et tuiles.

Le PDF est lu sur ce poste (PyMuPDF), puis écrit dans la base SIRV2 :
- dbo.schemas_unifilaires (schéma, graphe des lignes),
- dbo.schema_unifilaire_postes (postes, libellés, poste SIRV2 rapproché par le nom),
- dbo.schema_unifilaire_tuiles (images d'affichage).

Une nouvelle version d'un schéma (même --nom) remplace l'ancienne ; les associations faites à la main
dans la visionneuse (poste du schéma → poste SIRV2) sont reprises sur les postes de même libellé.

Prérequis : pip install pymupdf pillow

Usage (poste SENELEC, accès à la base SIRV2) :
    python scripts/migration/import_schema_unifilaire.py "D:\\Schemas\\SCHEMA_RI_DAKAR.pdf" --nom "Dakar (BCC)" --region Dakar
        → simulation : lecture du PDF, rapprochement, rapport CSV ; rien n'est écrit
    python scripts/migration/import_schema_unifilaire.py "D:\\Schemas\\SCHEMA_RI_DAKAR.pdf" --nom "Dakar (BCC)" --region Dakar --execute
        → écrit (sauvegarder la base avant)
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401,E402
from sqlalchemy import bindparam, text  # noqa: E402

from app.services.schema_unifilaire_rapprochement import cle_poste, rapprocher  # noqa: E402
from scripts.migration.config import get_settings  # noqa: E402
from scripts.migration.db_session import get_session  # noqa: E402
from scripts.migration.schema_unifilaire.extraction import extraire, tuiles, zoom_max  # noqa: E402

LOT_TUILES = 200


def _region_id(session, nom: str | None) -> int | None:  # noqa: ANN001
    if not nom:
        return None
    ligne = session.execute(
        text("SELECT TOP 1 id FROM dbo.regions WHERE libelle LIKE :n OR code LIKE :n ORDER BY id"),
        {"n": f"{nom}%"},
    ).first()
    if ligne is None:
        raise SystemExit(f"Région « {nom} » introuvable dans dbo.regions")
    return int(ligne[0])


def _tables_presentes(session) -> bool:  # noqa: ANN001
    return (
        session.execute(text("SELECT OBJECT_ID('dbo.schema_unifilaire_tuiles', 'U')")).scalar() is not None
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", help="Chemin du PDF du schéma unifilaire")
    parser.add_argument("--nom", help="Nom affiché (par défaut : nom du fichier) ; même nom = nouvelle version")
    parser.add_argument("--region", help="Région d'exploitation (Dakar, Régions) : schéma proposé à ses agents")
    parser.add_argument("--execute", action="store_true", help="Écrit dans la base (sinon simulation)")
    args = parser.parse_args()

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print(f"Fichier introuvable : {pdf}")
        return 1
    nom = (args.nom or pdf.stem).strip()[:150]

    debut = time.time()
    print(f"Lecture de {pdf.name} (une à deux minutes pour un grand schéma)…")
    schema = extraire(str(pdf))
    s = schema.stats
    print(
        f"  {s['postes']} postes, dont {s['postes_nommes']} avec un libellé ; {s['organes']} organes ;"
        f" graphe : {s['noeuds']} nœuds, {s['aretes']} tronçons ({time.time() - debut:.0f} s)"
    )

    with get_session() as session:
        if not _tables_presentes(session):
            print("Les tables des schémas unifilaires n'existent pas : appliquez d'abord la migration")
            print("(sur le serveur : dcs exec api alembic upgrade head).")
            return 1
        region_id = _region_id(session, args.region)
        postes_sirv2 = session.execute(text("SELECT id, libelle, code FROM dbo.postes WHERE is_active = 1")).all()
        libelles = [p.libelle for p in schema.postes]
        rapproches = rapprocher(libelles, [(int(i), lib, code) for i, lib, code in postes_sirv2])

        # Associations manuelles de la version précédente : reprises sur le même libellé
        ancien = session.execute(
            text("SELECT id FROM dbo.schemas_unifilaires WHERE nom = :nom"), {"nom": nom}
        ).scalars().all()
        manuels: dict[str, int] = {}
        if ancien:
            for libelle, poste_id in session.execute(
                text(
                    "SELECT libelle, poste_id FROM dbo.schema_unifilaire_postes"
                    " WHERE rapprochement = 'manuel' AND poste_id IS NOT NULL AND schema_id IN :ids"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": list(ancien)},
            ).all():
                if libelle:
                    manuels[cle_poste(libelle)] = int(poste_id)
        for i, libelle in enumerate(libelles):
            cle = cle_poste(libelle)
            if cle in manuels:
                rapproches[i] = (manuels[cle], "manuel")

        relies = sum(1 for pid, _ in rapproches if pid)
        ambigus = sum(1 for _, st in rapproches if st == "ambigu")
        nommes = sum(1 for lib in libelles if lib)
        print(
            f"Rapprochement avec les postes SIRV2 : {relies} reliés sur {nommes} postes nommés,"
            f" {ambigus} noms portés par plusieurs postes (à choisir dans la visionneuse)"
        )

        rapport = get_settings().reports_dir / f"schema_unifilaire_{pdf.stem}.csv"
        rapport.parent.mkdir(parents=True, exist_ok=True)
        ids_libelle = {int(i): lib for i, lib, _ in postes_sirv2}
        with rapport.open("w", encoding="utf-8-sig", newline="") as f:
            ecrivain = csv.writer(f, delimiter=";")
            ecrivain.writerow(["rang", "libelle_schema", "poste_sirv2_id", "poste_sirv2", "rapprochement"])
            for i, (p, (pid, statut)) in enumerate(zip(schema.postes, rapproches)):
                ecrivain.writerow([i, p.libelle or "", pid or "", ids_libelle.get(pid, "") if pid else "", statut or ""])
        print(f"Détail : {rapport}")

        if not args.execute:
            print("Simulation : rien n'a été écrit. Relancez avec --execute après une sauvegarde de la base.")
            return 0

        for ancien_id in ancien:
            session.execute(text("DELETE FROM dbo.schema_unifilaire_tuiles WHERE schema_id = :i"), {"i": ancien_id})
            session.execute(text("DELETE FROM dbo.schema_unifilaire_postes WHERE schema_id = :i"), {"i": ancien_id})
            session.execute(text("DELETE FROM dbo.schemas_unifilaires WHERE id = :i"), {"i": ancien_id})
        if ancien:
            print(f"Ancienne version remplacée ({len(ancien)}).")

        graphe = gzip.compress(json.dumps(schema.graphe_json(), separators=(",", ":")).encode("utf-8"))
        schema_id = session.execute(
            text(
                "INSERT INTO dbo.schemas_unifilaires (nom, fichier, region_id, largeur, hauteur, zoom_max, graphe,"
                " nb_postes, is_active) OUTPUT INSERTED.id VALUES (:nom, :fichier, :region, :l, :h, :z, :g, :n, 1)"
            ),
            {
                "nom": nom,
                "fichier": pdf.name[:255],
                "region": region_id,
                "l": schema.largeur,
                "h": schema.hauteur,
                "z": zoom_max(schema.largeur, schema.hauteur),
                "g": graphe,
                "n": len(schema.postes),
            },
        ).scalar_one()

        lignes = []
        for i, (p, (pid, statut)) in enumerate(zip(schema.postes, rapproches)):
            lb = p.libelle_bbox or (None, None, None, None)
            lignes.append(
                {
                    "s": schema_id, "r": i, "lib": (p.libelle or None) and p.libelle[:200], "f": p.forme,
                    "kva": p.puissance_kva, "x0": p.x0, "y0": p.y0, "x1": p.x1, "y1": p.y1,
                    "lx0": lb[0], "ly0": lb[1], "lx1": lb[2], "ly1": lb[3], "pid": pid, "st": statut,
                }
            )
        session.execute(
            text(
                "INSERT INTO dbo.schema_unifilaire_postes (schema_id, rang, libelle, forme, puissance_kva,"
                " x0, y0, x1, y1, lx0, ly0, lx1, ly1, poste_id, rapprochement) VALUES (:s, :r, :lib, :f, :kva,"
                " :x0, :y0, :x1, :y1, :lx0, :ly0, :lx1, :ly1, :pid, :st)"
            ),
            lignes,
        )
        print(f"{len(lignes)} postes écrits. Tuiles d'affichage…")

        lot: list[dict[str, object]] = []
        nb = 0
        for z, x, y, contenu in tuiles(str(pdf)):
            lot.append({"s": schema_id, "z": z, "x": x, "y": y, "c": contenu})
            if len(lot) >= LOT_TUILES:
                session.execute(
                    text("INSERT INTO dbo.schema_unifilaire_tuiles (schema_id, z, x, y, contenu) VALUES (:s, :z, :x, :y, :c)"),
                    lot,
                )
                nb += len(lot)
                lot = []
        if lot:
            session.execute(
                text("INSERT INTO dbo.schema_unifilaire_tuiles (schema_id, z, x, y, contenu) VALUES (:s, :z, :x, :y, :c)"),
                lot,
            )
            nb += len(lot)
        print(f"{nb} tuiles écrites. Schéma n° {schema_id} « {nom} » importé en {time.time() - debut:.0f} s.")
    return 0


if __name__ == "__main__":
    scripts.migration._bootstrap.terminer(main())
